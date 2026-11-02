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

Spec 0.3 adds two domain senses, promoted from the Phase 4
completeness probes (docs/completeness-probes-2026-11-02.md):
`contention` (interval contention over committed bookings) and
`authority` (grant ceilings proven from operator executions).
Readings are published values: refold reproduces state from the
log, and a reading is a pure function of the entry prefix up to
its as_of_seq plus its parameters, so recomputation at that
position reproduces it.
"""
from .records import outputs_and_uses

DRIFT_WINDOW = 25

#: Seats that contend with themselves on the booking board.
#: "box" contends with every seat; "detached" contends with
#: nothing and is the one classified non-exclusive seat.
EXCLUSIVE_SEATS = {"zcode", "mcode", "claude-code", "gpu", "stage",
                   "kimi", "box"}

CONTENTION_METHOD = (
    "contention sense: read set = committed units with prefix "
    "booking/<box>/ (the subject's box); a committed booking "
    "contends iff ALL of: status is \"active\" only (done, "
    "cancelled, preempted and expired bookings are inert); its "
    "id differs from the candidate's id (a booking never "
    "contends with itself -- a committed row whose id equals "
    "the candidate's id is excluded even when its producer "
    "differs); its producer differs from the candidate's "
    "producer (a same-producer overlap is a renewal, not "
    "contention); its checkby is null or >= the candidate start "
    "(a booking whose check-by passed before the candidate "
    "starts is dead by the board protocol); seat rules -- equal "
    "seats contend iff the seat is in {zcode, mcode, "
    "claude-code, gpu, stage, kimi, box}, \"box\" contends with "
    "every seat, other distinct seats do not contend; and "
    "strict interval overlap candidate.start < other.end and "
    "other.start < candidate.end (touching endpoints do not "
    "contend). Value reports every contender sorted by id, "
    "their count, the maximum contender rank (-1 when none), "
    "the highest-rank contender's id (ties: smallest id, null "
    "when none), and \"unclassified\": the sorted seat strings "
    "-- the candidate's seat and the seats of status-\"active\" "
    "rows under the prefix -- that are in neither the exclusive "
    "set nor {\"detached\"}. Rank otherwise plays no part in "
    "contention itself."
)

AUTHORITY_METHOD = (
    "authority sense: read set = log entries passing three "
    "filters -- entry kind is \"execution\", the entry body's "
    "producer is \"operator\", and the entry's applied writes "
    "include a write to unit authority/<producer>. Among those "
    "writes the LATEST wins: its value (an integer) is the "
    "ceiling, so a later lower grant is a downward revocation; "
    "grants is the count of such writes. Only operator-authored "
    "writes count: a producer's own write to authority/<self> "
    "may land in units under policy/1 but fails the producer "
    "filter, so it is visible in the log and inert here. The "
    "unit's current value alone is not evidence of a grant. No "
    "operator grant -> ceiling null, grants 0."
)


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


def _seats_conflict(candidate_seat, other_seat):
    if candidate_seat == other_seat:
        return candidate_seat in EXCLUSIVE_SEATS
    if "box" in (candidate_seat, other_seat):
        return True
    return False


def _contention(entries, state, subject, runtime):
    """Subject: <box>/<seat>/<start>/<end>/<producer>/<id>,
    parsed from the right so the box may itself contain "/"."""
    if not subject:
        raise ValueError("contention sense needs a subject")
    parts = subject.rsplit("/", 5)
    if len(parts) != 6:
        raise ValueError(
            "contention subject must be "
            "<box>/<seat>/<start>/<end>/<producer>/<id>: %r" % subject)
    box, seat, start, end, producer, cand_id = parts
    try:
        cand_start, cand_end = int(start), int(end)
    except ValueError:
        raise ValueError(
            "contention subject start/end must be integer minutes: "
            "%r" % subject)
    prefix = "booking/%s/" % box
    contenders = []
    seats_seen = {seat}
    for unit in sorted(state.units):
        if not unit.startswith(prefix):
            continue
        other = state.units[unit]
        if not isinstance(other, dict):
            continue
        if other.get("status") != "active":
            continue
        if isinstance(other.get("seat"), str):
            seats_seen.add(other["seat"])
        if other.get("id") == cand_id:
            continue
        if other.get("producer") == producer:
            continue
        checkby = other.get("checkby")
        if checkby is not None and checkby < cand_start:
            continue
        if not _seats_conflict(seat, other.get("seat")):
            continue
        if not (cand_start < other["end"]
                and other["start"] < cand_end):
            continue
        contenders.append({"id": other["id"],
                           "producer": other["producer"],
                           "seat": other["seat"],
                           "start": other["start"],
                           "end": other["end"],
                           "rank": other.get("rank", 0)})
    contenders.sort(key=lambda c: c["id"])
    if contenders:
        max_rank = max(c["rank"] for c in contenders)
        top_id = min(c["id"] for c in contenders
                     if c["rank"] == max_rank)
    else:
        max_rank = -1
        top_id = None
    unclassified = sorted(
        s for s in seats_seen
        if s not in EXCLUSIVE_SEATS and s != "detached")
    return {"value": {"contenders": contenders,
                      "count": len(contenders),
                      "max_rank": max_rank,
                      "top_id": top_id,
                      "unclassified": unclassified},
            "method": CONTENTION_METHOD}


def _authority(entries, state, subject, runtime):
    """Subject: the producer whose grant ceiling is read."""
    if not subject:
        raise ValueError("authority sense needs a producer subject")
    unit = "authority/%s" % subject
    ceiling = None
    grants = 0
    for entry in entries:
        if entry["kind"] != "execution":
            continue
        body = entry["body"]
        if body.get("producer") != "operator":
            continue
        for applied in body.get("applied", []):
            if applied.get("verb") == "write" \
                    and applied["args"][0] == unit:
                ceiling = applied["args"][1]
                grants += 1
    return {"value": {"ceiling": ceiling, "grants": grants},
            "method": AUTHORITY_METHOD}


SENSES = {
    "queue-depth": _queue_depth,
    "output-use": _output_use,
    "starvation": _starvation,
    "calibration-drift": _calibration_drift,
    "contention": _contention,
    "authority": _authority,
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
