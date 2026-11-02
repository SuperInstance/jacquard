"""Senses: named readings over the record (SPEC section 11).

A sense is a read-only projection of the log and folded state,
published under a name with its method stated. Computing a sense
appends nothing; publishing writes a `sense` entry whose value is
{"value", "method", "as_of_seq"}. Everything a decision could
consult arrives this way — evidence with its derivation attached,
never a bare number. Values are canonical types only (integers,
strings, bools, lists, maps): rates are integer basis points.

Built-in senses generalise the Phase 1 records projection:
per-producer output-use, queue depth, starvation evidence from a
live scheduler, and a calibration-drift stub (kernel-wide
decision-rate drift over fixed windows — real per-rule
calibration arrives with the learner, and the method says so).
Decision-model readings enter through the same door, via the
provider seam (providers.py), as senses like any other.
"""
from .records import outputs_and_uses

DRIFT_WINDOW = 25


def _queue_depth(entries, state, subject, runtime):
    return {"value": len(state.decision_queue),
            "method": "count of folded decision_queue entries"}


def _output_use(entries, state, subject, runtime):
    if not subject:
        raise ValueError("output-use sense needs a producer subject")
    outputs, used = outputs_and_uses(entries, subject)
    ratio_bp = (10000 * used) // outputs if outputs else 0
    return {"value": {"producer": subject, "outputs": outputs,
                      "used": used, "ratio_bp": ratio_bp},
            "method": "records projection: outputs listed on executed "
                      "proposals vs outputs named in later proposals' uses"}


def _starvation(entries, state, subject, runtime):
    scheduler = (runtime or {}).get("scheduler")
    if scheduler is None:
        return {"value": {"status": "no-runtime"},
                "method": "starvation evidence needs a live scheduler's "
                          "counters; none was supplied at publish time"}
    stats = scheduler.stats()
    flows = {("%s/%s" % flow): {"waiting": data["waiting"],
                                "served_size": data["served_size"],
                                "weight_bp": int(10000 * data["weight"])}
             for flow, data in stats["flows"].items()}
    return {"value": {"virtual_time": int(stats["virtual_time"]),
                      "flows": flows},
            "method": "scheduler counters at publish time: per-flow "
                      "waiting items, served size, current weight"}


def _calibration_drift(entries, state, subject, runtime):
    outcomes = [e["body"]["outcome"] for e in entries
                if e["kind"] == "decision"
                and e["body"].get("outcome") in ("allow", "deny")]
    if len(outcomes) < 2 * DRIFT_WINDOW:
        return {"value": {"status": "insufficient-data",
                          "decisions": len(outcomes)},
                "method": "stub: needs %d decisions for two windows"
                          % (2 * DRIFT_WINDOW)}
    baseline = outcomes[:DRIFT_WINDOW]
    recent = outcomes[-DRIFT_WINDOW:]

    def allow_bp(window):
        return (10000 * window.count("allow")) // len(window)

    drift = abs(allow_bp(recent) - allow_bp(baseline))
    return {"value": {"status": "stub", "drift_bp": drift,
                      "baseline_allow_bp": allow_bp(baseline),
                      "recent_allow_bp": allow_bp(recent),
                      "window": DRIFT_WINDOW},
            "method": "stub: kernel-wide allow-rate drift between the "
                      "first and last %d decisions; per-rule calibration "
                      "arrives with the learner" % DRIFT_WINDOW}


SENSES = {
    "queue-depth": _queue_depth,
    "output-use": _output_use,
    "starvation": _starvation,
    "calibration-drift": _calibration_drift,
}


def compute_sense(name, entries, state, runtime=None):
    """Compute a reading. Read-only: appends nothing, folds
    nothing. `name` may carry a subject: "output-use:<producer>"."""
    base, _, subject = name.partition(":")
    if base not in SENSES:
        raise ValueError("unknown sense: %s" % name)
    reading = SENSES[base](entries, state, subject or None, runtime)
    return {"value": reading["value"], "method": reading["method"],
            "as_of_seq": (entries[-1]["seq"] if entries else -1)}


def publish_senses(sequencer, names, runtime=None, producer="operator"):
    """Compute each named sense against the sequencer's current
    record and publish it as a sense entry. Returns the entries."""
    published = []
    for name in names:
        reading = compute_sense(name, sequencer.log.entries,
                                sequencer.state, runtime)
        published.append(sequencer.submit_sense(name, reading, producer))
    return published
