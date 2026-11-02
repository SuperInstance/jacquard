"""Probe A driver: kernel machinery only, routing by this module.

Every decision-relevant predicate is evaluated by the kernel --
the contention *sense* (contention_sense.py) computes contention
over committed state, dictionary *words* below turn a published
reading into guard booleans, and the booking *machine*'s guards
decide transitions. This module computes NO overlap and NO rank
arithmetic: it builds sense names, submits envelopes, creates
machine instances and steps them.

Words (all (map -> bool), payload carries {"sense_name", ...};
remember state.senses[name] is the reading dict
{"value", "method", "as_of_seq"}, hence sense -> getf "value"
-> getf <field>):

- ``booking-clear``     -- sense value count == 0
- ``booking-contended`` -- sense value count > 0
- ``booking-outranks``  -- count > 0 AND payload rank > value max_rank
- ``booking-tied``      -- count > 0 AND payload rank > 0 AND
                           payload rank == value max_rank

``booking-outranks`` / ``booking-tied`` use the dictionary's
``if`` form for conjunction: a gate condition is computed with
the payload and the sense value preserved beneath it; the true
branch computes the next condition from what is preserved, the
false branch drops both and answers False. Branch stack shapes
agree, as the dictionary's simulator requires.
"""
import copy

from jacquard import install_lifecycles, make_envelope, publish_senses

from contention_sense import register as _register_sense

# payload (map) -> sense value (map): the shared prefix.
_TO_VALUE = [{"lit": "sense_name"}, "getf", "sense",
             {"lit": "value"}, "getf"]
# payload preserved under the value: [payload, value]
_TO_VALUE_KEPT = ["dup"] + _TO_VALUE
_COUNT_GT0 = [{"lit": "count"}, "getf", {"lit": 0}, "gt"]
_DROP2_FALSE = ["drop", "drop", {"lit": False}]


def _sense_example(name, count, max_rank, extra_payload=None,
                   expect=True):
    payload = {"sense_name": name}
    if extra_payload:
        payload.update(extra_payload)
    value = {"contenders": [], "count": count, "max_rank": max_rank,
             "top_id": None}
    return {"args": [payload],
            "state": {"senses": {name: {"value": value,
                                        "method": "example",
                                        "as_of_seq": 0}}},
            "expect": [expect]}


def _definitions():
    clear = {
        "name": "booking-clear",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": _TO_VALUE + [{"lit": "count"}, "getf",
                             {"lit": 0}, "eq"],
        "examples": [
            _sense_example("contention:ex", 0, -1, expect=True),
            _sense_example("contention:ex", 2, 0, expect=False)],
    }
    contended = {
        "name": "booking-contended",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": _TO_VALUE + _COUNT_GT0,
        "examples": [
            _sense_example("contention:ex", 0, -1, expect=False),
            _sense_example("contention:ex", 2, 0, expect=True)],
    }
    # [P, V] -> rank > max_rank, from the preserved pair.
    _rank_gt_max = ["swap", "dup", {"lit": "rank"}, "getf", "swap",
                    "drop", "swap", {"lit": "max_rank"}, "getf", "gt"]
    outranks = {
        "name": "booking-outranks",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": _TO_VALUE_KEPT + ["dup"] + _COUNT_GT0 + [
            {"if": _rank_gt_max, "else": list(_DROP2_FALSE)}],
        "examples": [
            _sense_example("contention:ex", 2, 3, {"rank": 5},
                           expect=True),
            _sense_example("contention:ex", 2, 7, {"rank": 5},
                           expect=False),
            _sense_example("contention:ex", 0, -1, {"rank": 5},
                           expect=False)],
    }
    # Nested gate inside the true branch: [P, V] --swap/dup-->
    # rank > 0 with [V, P] preserved, then rank == max_rank
    # computed from [V, P].
    _rank_eq_max = ["dup", {"lit": "rank"}, "getf", "swap", "drop",
                    "swap", {"lit": "max_rank"}, "getf", "eq"]
    _tied_true = ["swap", "dup", {"lit": "rank"}, "getf",
                  {"lit": 0}, "gt",
                  {"if": _rank_eq_max, "else": list(_DROP2_FALSE)}]
    tied = {
        "name": "booking-tied",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": _TO_VALUE_KEPT + ["dup"] + _COUNT_GT0 + [
            {"if": _tied_true, "else": list(_DROP2_FALSE)}],
        "examples": [
            _sense_example("contention:ex", 2, 3, {"rank": 3},
                           expect=True),
            _sense_example("contention:ex", 2, 5, {"rank": 3},
                           expect=False),
            _sense_example("contention:ex", 1, 0, {"rank": 0},
                           expect=False),
            _sense_example("contention:ex", 0, -1, {"rank": 3},
                           expect=False)],
    }
    return [clear, contended, outranks, tied]


BOOKING_MACHINE = """\
machine booking
initial: requested
terminal: done, cancelled, preempted, expired
events: commit, tie, preempt, cancel, complete, expire
requested -> active : commit [booking-clear]
requested -> held : commit otherwise
requested -> held : tie [booking-tied]
held -> active : commit [booking-clear]
held -> preempted : preempt
held -> expired : expire
held -> cancelled : cancel
active -> preempted : preempt
active -> done : complete
active -> cancelled : cancel
requested -> cancelled : cancel
ignore commit in *
ignore tie in *
ignore preempt in *
ignore cancel in *
ignore complete in *
ignore expire in *
"""


def install(seq):
    """Install lifecycles, the four guard words and the booking
    machine on a Sequencer. Returns all verdicts; raises if any
    submission was refused (fail loud, never half-installed)."""
    _register_sense()
    verdicts = {"lifecycles": install_lifecycles(seq),
                "definitions": {}, "machine": None}
    for defn in _definitions():
        verdict = seq.submit(make_envelope(
            "operator", "definition", defn, [],
            "probe-a-def-" + defn["name"]))
        verdicts["definitions"][defn["name"]] = verdict
        if verdict["status"] != "accepted":
            raise RuntimeError("definition %s refused: %r"
                               % (defn["name"], verdict))
    verdict = seq.submit(make_envelope(
        "operator", "machine", {"text": BOOKING_MACHINE}, [],
        "probe-a-machine-booking"))
    verdicts["machine"] = verdict
    if verdict["status"] != "accepted":
        raise RuntimeError("booking machine refused: %r" % (verdict,))
    return verdicts


def publish_contention(seq, candidate):
    """Build the candidate's contention sense name and publish
    the reading against current committed state. Returns the
    sense name. Publishing at decision time is the pinned
    requirement (see the staleness test): guards read the
    published reading, not a live recomputation."""
    _register_sense()
    name = "contention:%s/%s/%s/%s/%s/%s" % (
        candidate["box"], candidate["seat"], candidate["start"],
        candidate["end"], candidate["producer"], candidate["id"])
    publish_senses(seq, [name])
    return name


def shadow_decide(seq, candidate):
    """-> "allow" | "queue": publish the contention sense, then
    let the booking machine's commit transition (guarded by
    booking-clear, with the otherwise fallback to held) decide."""
    name = publish_contention(seq, candidate)
    instance = "booking:%s" % candidate["id"]
    if instance not in seq.state.machine_instances:
        seq.create_machine_instance("booking", instance)
    payload = {**candidate, "sense_name": name,
               "rank": candidate["rank"]}
    seq.step_machine(instance, "commit", payload)
    return "allow" if seq.machine_instance_state(instance) == "active" \
        else "queue"


def commit_booking_record(seq, booking):
    """Commit a booking record as board reality: a proposal
    (producer = the booking's producer, class "booking") writing
    unit booking/<box>/<id>. Independent of any shadow decision
    -- the board took every row; later candidates contend
    against what is committed here."""
    unit = "booking/%s/%s" % (booking["box"], booking["id"])
    envelope = make_envelope(
        booking["producer"], "proposal",
        {"class": "booking",
         "requests": [{"verb": "write",
                       "args": [unit, copy.deepcopy(booking)]}]},
        ["write"], "probe-a-" + booking["id"])
    return seq.submit(envelope)


def set_booking_status(seq, booking_id, box, new_status,
                       current_booking):
    """Operator proposal replacing the committed record's status.
    Idem is unique per call (derived from the log length, which
    every submission advances)."""
    updated = {**current_booking, "status": new_status}
    unit = "booking/%s/%s" % (box, booking_id)
    envelope = make_envelope(
        "operator", "proposal",
        {"class": "booking",
         "requests": [{"verb": "write", "args": [unit, updated]}]},
        ["write"], "probe-a-status-%s-%d" % (booking_id,
                                             len(seq.log.entries)))
    return seq.submit(envelope)
