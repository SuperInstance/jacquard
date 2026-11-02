"""The booking profile (SPEC section 11.4): definitions and a
flow, not kernel code.

The booking board's rules shipped as data: a parameterised
contention sense and an authority sense (both kernel-resident,
in senses.py), seven dictionary words, one lifecycle machine,
and this flow module routing between them. Every
decision-relevant predicate is evaluated by the kernel — the
contention sense computes contention over committed state, the
authority sense computes grant ceilings from operator
executions alone, the words turn published readings into guard
booleans and the effective rank, and the booking machine's
guards decide transitions. This module computes no overlap and
no rank comparison in Python: it builds sense names, submits
envelopes, creates machine instances and steps them. (Reading
a published sense's contender list to know WHOM to preempt is
routing over kernel-computed data.)

The booking record schema: {"id", "box", "producer", "seat",
"start", "end", "checkby", "status", "rank", "asserted_rank"}
— "rank" is the EFFECTIVE rank (the asserted rank clamped to
the granted ceiling, 0 with no grant); the asserted rank is
kept beside it so the record never launders a claim into a
fact.
"""
import copy

from .envelope import envelope_hash, make_envelope
from .lifecycles import install_lifecycles
from .senses import publish_senses
from .state import Refusal

# ---------------------------------------------------------- machine

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

# ---------------------------------------------------------- words
# Payload (map) -> sense value (map): the shared prefix.
# state.senses[name] is the reading dict {"value", "method",
# "as_of_seq"}, hence sense -> getf "value" -> getf <field>.

_TO_VALUE = [{"lit": "sense_name"}, "getf", "sense",
             {"lit": "value"}, "getf"]
# Payload preserved under the value: [payload, value]
_TO_VALUE_KEPT = ["dup"] + _TO_VALUE
_COUNT_GT0 = [{"lit": "count"}, "getf", {"lit": 0}, "gt"]
_DROP2_FALSE = ["drop", "drop", {"lit": False}]


def _sense_example(name, count, max_rank, extra_payload=None,
                   expect=True, unclassified=None):
    payload = {"sense_name": name}
    if extra_payload:
        payload.update(extra_payload)
    value = {"contenders": [], "count": count, "max_rank": max_rank,
             "top_id": None,
             "unclassified": list(unclassified or [])}
    return {"args": [payload],
            "state": {"senses": {name: {"value": value,
                                        "method": "example",
                                        "as_of_seq": 0}}},
            "expect": [expect]}


def _booking_definitions():
    clear = {
        "name": "booking-clear",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        # count == 0 AND the reading's unclassified seat list is
        # empty: an unclassified seat fails closed (the booking
        # is held for a human, never silently cleared).
        "body": _TO_VALUE + [
            "dup", {"lit": "count"}, "getf", {"lit": 0}, "eq",
            "swap", {"lit": "unclassified"}, "getf", "count",
            {"lit": 0}, "eq", "and"],
        "examples": [
            _sense_example("contention:ex", 0, -1, expect=True),
            _sense_example("contention:ex", 2, 0, expect=False),
            _sense_example("contention:ex", 0, -1, expect=False,
                           unclassified=["zcod"])],
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


# [payload] -> [ceiling, rank]: build the authority sense name
# from the payload's producer, read the published reading, and
# extract its ceiling alongside the payload's asserted rank.
_TO_CEILING_RANK = [
    "dup", {"lit": "producer"}, "getf",
    {"lit": "authority:"}, "swap", "cat", "sense",
    {"lit": "value"}, "getf", {"lit": "ceiling"}, "getf",
    "swap", {"lit": "rank"}, "getf",
]

# From [ceiling, rank]: swap to [rank, ceiling], duplicate the
# ceiling, and leave [rank, ceiling, ceiling-is-not-null] -- the
# gate both ceiling words branch on.
_NULL_GATE = ["swap", "dup", {"lit": None}, "eq", "not"]
_DROP2 = ["drop", "drop"]


def _authority_example(producer, ceiling, grants, rank, expect):
    name = "authority:%s" % producer
    payload = {"producer": producer, "rank": rank,
               "sense_name": name}
    reading = {"value": {"ceiling": ceiling, "grants": grants},
               "method": "example", "as_of_seq": 0}
    return {"args": [payload],
            "state": {"senses": {name: reading}},
            "expect": [expect]}


def _rank_definitions():
    rank_granted = {
        "name": "rank-granted",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        # then: [rank, ceiling] -> rank > ceiling -> not (<=);
        # else: drop both, answer False (no grant).
        "body": _TO_CEILING_RANK + _NULL_GATE + [
            {"if": ["gt", "not"],
             "else": _DROP2 + [{"lit": False}]}],
        "examples": [
            _authority_example("captain", 5, 1, 5, True),
            _authority_example("captain", 5, 1, 3, True),
            _authority_example("captain", 5, 1, 6, False),
            _authority_example("mallory", None, 0, 9, False),
            _authority_example("mallory", None, 0, 0, False)],
    }
    effective_rank = {
        "name": "effective-rank",
        "signature": {"ins": ["map"], "outs": ["int"]},
        # then: [rank, ceiling] -> min2 (the clamp);
        # else: drop both, answer 0 (no grant).
        "body": _TO_CEILING_RANK + _NULL_GATE + [
            {"if": ["min2"],
             "else": _DROP2 + [{"lit": 0}]}],
        "examples": [
            _authority_example("captain", 5, 1, 5, 5),
            _authority_example("captain", 5, 1, 3, 3),
            _authority_example("captain", 2, 1, 5, 2),
            _authority_example("mallory", None, 0, 9, 0)],
    }
    rank_below = {
        "name": "rank-below",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["dup", {"lit": "rank"}, "getf", "swap",
                 {"lit": "limit"}, "getf", "lt"],
        "examples": [
            {"args": [{"rank": 0, "limit": 5}], "expect": [True]},
            {"args": [{"rank": 5, "limit": 5}], "expect": [False]},
            {"args": [{"rank": 7, "limit": 5}], "expect": [False]}],
    }
    return [rank_granted, effective_rank, rank_below]


def install_booking(seq):
    """Install the booking profile on a sequencer: the lifecycle
    machines, the seven guard/rank words and the booking
    machine. Returns all verdicts; raises if any submission was
    refused (fail loud, never half-installed)."""
    verdicts = {"lifecycles": install_lifecycles(seq),
                "definitions": {}, "machine": None}
    for defn in _booking_definitions() + _rank_definitions():
        verdict = seq.submit(make_envelope(
            "operator", "definition", copy.deepcopy(defn), [],
            "booking-def-" + defn["name"]))
        verdicts["definitions"][defn["name"]] = verdict
        if verdict["status"] != "accepted":
            raise RuntimeError("definition %s refused: %r"
                               % (defn["name"], verdict))
        if verdict["computed_effects"] != []:
            raise RuntimeError("definition %s must be pure, got %r"
                               % (defn["name"], verdict))
    verdict = seq.submit(make_envelope(
        "operator", "machine", {"text": BOOKING_MACHINE}, [],
        "booking-machine"))
    verdicts["machine"] = verdict
    if verdict["status"] != "accepted":
        raise RuntimeError("booking machine refused: %r" % (verdict,))
    return verdicts


# ---------------------------------------------------------- senses

def publish_contention(seq, candidate):
    """Build the candidate's contention sense name and publish
    the reading against current committed state. Returns the
    sense name. Publishing at decision time is required: guards
    read the published reading, not a live recomputation.
    Candidate fields that carry "/" would mis-split the
    positional subject grammar, so they are refused by name
    (FIELD) instead of misparsed silently."""
    for field in ("box", "seat", "producer", "id"):
        if "/" in str(candidate[field]):
            raise Refusal(
                "FIELD", "booking candidate field %s must not "
                "contain \"/\": %r" % (field, candidate[field]))
    name = "contention:%s/%s/%s/%s/%s/%s" % (
        candidate["box"], candidate["seat"], candidate["start"],
        candidate["end"], candidate["producer"], candidate["id"])
    publish_senses(seq, [name])
    return name


def publish_authority(seq, producer):
    """Publish the authority reading for `producer` against
    current committed state. Returns the sense name,
    "authority:<producer>". Publishing at decision time is
    required: the rank words read the published reading."""
    name = "authority:%s" % producer
    publish_senses(seq, [name])
    return name


def _eval_word(seq, name, payload):
    stack, requests = seq.evaluate_word(name, "operator", [payload])
    if requests or len(stack) != 1:
        raise RuntimeError("word %s returned stack=%r requests=%r"
                           % (name, stack, requests))
    return stack[0]


def effective_rank(seq, producer, asserted):
    """The rank a booking by `producer` asserting `asserted`
    would commit with, computed by the effective-rank word
    against a freshly published authority reading."""
    name = publish_authority(seq, producer)
    return _eval_word(seq, "effective-rank",
                      {"producer": producer, "rank": asserted,
                       "sense_name": name})


# ---------------------------------------------------------- flow

def _unique_idem(seq, prefix):
    return "%s-%d" % (prefix, len(seq.log.entries))


def _preemption_record(seq, winner_booking, rank, authority_name):
    return {"winner": winner_booking["id"],
            "winner_producer": winner_booking["producer"],
            "rank": rank,
            "authority_sense": authority_name,
            "at_seq": seq.log.entries[-1]["seq"] if seq.log.entries
            else -1}


def _queued_pid_for_unit(seq, unit):
    for proposal_id, queued in seq.state.decision_queue.items():
        for request in queued.get("requests", []):
            if request.get("verb") == "write" \
                    and request["args"][0] == unit:
                return proposal_id
    return None


def _step_preempt(seq, loser_id, winner_booking):
    instance = "booking:%s" % loser_id
    if instance in seq.state.machine_instances:
        seq.step_machine(instance, "preempt",
                         {"winner": winner_booking["id"],
                          "winner_producer":
                          winner_booking["producer"]})


class BookingFlow:
    """The live booking flow over one sequencer. A live booking
    proposal always carries a notify request alongside its
    write, so policy/1 queues every live booking and the flow
    always has a decision-queue entry to release or reject."""

    def __init__(self, seq):
        self.seq = seq

    # ------------------------------------------------ grants
    def grant(self, producer, ceiling):
        """An operator grant: proposal (class "config") writing
        authority/<producer> = ceiling. Policy/1 allows it at
        once, so the grant is an execution in the log — the
        only kind the authority sense counts."""
        seq = self.seq
        envelope = make_envelope(
            "operator", "proposal",
            {"class": "config",
             "requests": [{"verb": "write",
                           "args": ["authority/%s" % producer,
                                    int(ceiling)]}]},
            ["write"], _unique_idem(seq, "booking-grant-" + producer))
        return seq.submit(envelope)

    # ------------------------------------------------ live
    def submit_live(self, booking):
        """Submit one booking in live mode. `booking` carries
        the ASSERTED rank in "rank". Returns a routing report;
        the decisions themselves are the kernel's (senses,
        words, machine guards, policy queue)."""
        seq = self.seq
        booking = dict(booking)
        asserted = booking["rank"]
        contention_name = publish_contention(seq, booking)
        authority_name = publish_authority(seq, booking["producer"])
        effective = _eval_word(
            seq, "effective-rank",
            {"producer": booking["producer"], "rank": asserted,
             "sense_name": authority_name})
        record = {"id": booking["id"], "box": booking["box"],
                  "producer": booking["producer"],
                  "seat": booking["seat"], "start": booking["start"],
                  "end": booking["end"],
                  "checkby": booking.get("checkby"),
                  "status": "active", "rank": effective,
                  "asserted_rank": asserted}
        unit = "booking/%s/%s" % (booking["box"], booking["id"])
        envelope = make_envelope(
            booking["producer"], "proposal",
            {"class": "booking",
             "requests": [
                 {"verb": "write",
                  "args": [unit, copy.deepcopy(record)]},
                 {"verb": "notify",
                  "args": ["booking-channel", booking["id"]]}]},
            ["write", "notify"],
            _unique_idem(seq, "booking-live-" + booking["id"]))
        proposal_id = envelope_hash(envelope)

        instance = "booking:%s" % booking["id"]
        if instance not in seq.state.machine_instances:
            seq.create_machine_instance("booking", instance)
        word_payload = {"sense_name": contention_name,
                        "rank": effective}
        outranks = _eval_word(seq, "booking-outranks", word_payload)
        tied = _eval_word(seq, "booking-tied", word_payload)

        preempted = []
        if outranks:
            sense_value = seq.state.senses[contention_name]["value"]
            for contender in sense_value["contenders"]:
                self._preempt_active(contender, booking, effective,
                                     authority_name)
                preempted.append(contender["id"])
            # Republish at the new decision point: now clear.
            contention_name = publish_contention(seq, booking)
            seq.step_machine(
                instance, "commit",
                {**booking, "sense_name": contention_name,
                 "rank": effective})
        elif tied:
            seq.step_machine(
                instance, "tie",
                {**booking, "sense_name": contention_name,
                 "rank": effective})
        else:
            seq.step_machine(
                instance, "commit",
                {**booking, "sense_name": contention_name,
                 "rank": effective})

        verdict = seq.submit(envelope)
        if verdict.get("outcome") != "queue":
            raise RuntimeError("live booking %s was not queued by "
                               "policy/1: %r" % (booking["id"], verdict))
        release = None
        state = seq.machine_instance_state(instance)
        if state == "active":
            release = seq.release_queued(proposal_id, "booking-flow")
        return {"booking_id": booking["id"],
                "proposal_id": proposal_id,
                "effective_rank": effective,
                "asserted_rank": asserted,
                "contention_sense": contention_name,
                "authority_sense": authority_name,
                "machine_state": state, "preempted": preempted,
                "verdict": verdict, "release": release,
                "record": record}

    def _preempt_active(self, contender, winner_booking,
                        effective_rank, authority_name):
        """Preempt one ACTIVE contender: operator proposal
        (class "preemption") writing the loser's unit as
        preempted plus the preemption record, the instance
        stepped "preempt", and — defensively — a reject if the
        contender somehow still holds a queued proposal."""
        seq = self.seq
        loser_id = contender["id"]
        unit = "booking/%s/%s" % (winner_booking["box"], loser_id)
        current = seq.state.units[unit]
        record = _preemption_record(seq, winner_booking,
                                    effective_rank, authority_name)
        envelope = make_envelope(
            "operator", "proposal",
            {"class": "preemption",
             "requests": [
                 {"verb": "write",
                  "args": [unit, {**copy.deepcopy(current),
                                  "status": "preempted"}]},
                 {"verb": "write",
                  "args": ["preemption/%s" % loser_id, record]}]},
            ["write"],
            _unique_idem(seq, "booking-preempt-" + loser_id))
        verdict = seq.submit(envelope)
        if verdict.get("outcome") != "allow":
            raise RuntimeError("preemption of %s refused: %r"
                               % (loser_id, verdict))
        _step_preempt(seq, loser_id, winner_booking)
        queued_pid = _queued_pid_for_unit(seq, unit)
        if queued_pid is not None:
            seq.reject_queued(queued_pid, "booking-flow")
        return record

    # ------------------------------------------------ disposal
    def dispose(self, winner):
        """After `winner` (a committed booking record, its
        "rank" the effective rank) commits, dispose of HELD
        bookings it now outranks: reject each from the decision
        queue with reason "preempted-by:<winner-id>" (its write
        never executes), write its preemption record, and step
        its instance "preempt". Equal rank is left queued.
        Returns the disposed booking ids, in queue order."""
        seq = self.seq
        disposed = []
        snapshot = list(seq.state.decision_queue.items())
        for proposal_id, queued in snapshot:
            if proposal_id not in seq.state.decision_queue:
                continue
            loser = None
            for request in queued.get("requests", []):
                if request.get("verb") == "write" \
                        and request["args"][0].startswith("booking/"):
                    loser = request["args"][1]
            if not isinstance(loser, dict) or "id" not in loser:
                continue
            if loser["id"] == winner["id"]:
                continue
            name = publish_contention(seq, loser)
            value = seq.state.senses[name]["value"]
            if winner["id"] not in [c["id"]
                                    for c in value["contenders"]]:
                continue
            below = _eval_word(seq, "rank-below",
                               {"rank": loser["rank"],
                                "limit": winner["rank"]})
            if not below:
                continue  # tie or outranking holder: left queued
            self._dispose_queued(loser, proposal_id, winner)
            disposed.append(loser["id"])
        return disposed

    def _dispose_queued(self, loser_record, loser_pid, winner):
        seq = self.seq
        seq.reject_queued(loser_pid, "booking-flow",
                          reason="preempted-by:%s" % winner["id"])
        authority_name = publish_authority(seq, winner["producer"])
        record = _preemption_record(seq, winner, winner["rank"],
                                    authority_name)
        envelope = make_envelope(
            "operator", "proposal",
            {"class": "preemption",
             "requests": [{"verb": "write",
                           "args": ["preemption/%s"
                                    % loser_record["id"], record]}]},
            ["write"],
            _unique_idem(seq, "booking-dispose-" + loser_record["id"]))
        verdict = seq.submit(envelope)
        if verdict.get("outcome") != "allow":
            raise RuntimeError("disposal of %s refused: %r"
                               % (loser_record["id"], verdict))
        _step_preempt(seq, loser_record["id"], winner)
        return record
