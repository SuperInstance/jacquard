"""Probe C driver: the live booking flow with authority
priority. Kernel machinery decides, this module routes.

Every decision-relevant predicate is evaluated by the kernel:
the contention *sense* (Probe A) computes contention over
committed state, the authority *sense* (authority_sense.py)
computes grant ceilings from operator executions alone, the
dictionary *words* (booking-clear / booking-contended /
booking-outranks / booking-tied from Probe A; rank-granted /
effective-rank / rank-below from Probe C) turn published
readings into the booleans and the effective rank, and the
booking *machine*'s guards decide commit/tie transitions. This
module computes NO overlap and NO rank comparison in Python:
it publishes senses, evaluates words, steps machines, submits
envelopes and disposes of the decision queue. (Reading a
published sense's contender list to know WHOM to preempt is
routing over kernel-computed data -- the staged brief's own
wording: "they are in the sense value". The disposal pass's
rank comparison goes through the rank-below word.)

Live mode (the staged brief's design):

- A grant is an operator proposal (class "config") writing
  unit ``authority/<producer>`` = integer ceiling. Operator is
  the only producer whose executions the authority sense
  counts.
- A live booking proposal ALWAYS carries a notify request
  alongside its write, declared effects ["write", "notify"],
  so policy/1 queues every live booking (protected effect) and
  the flow always has a decision-queue entry to release or
  reject. The booking record the write carries stores the
  EFFECTIVE rank in "rank" (never the asserted one) and the
  asserted rank alongside it in "asserted_rank", so the queued
  decision entry shows both.
- ``submit_live`` publishes both senses at decision time,
  computes the effective rank by word, creates the booking
  instance, then routes:
    - booking-outranks (flow evaluates the word itself -- it is
      not a machine guard): preempt EVERY contender first (see
      ``_preempt_active``), republish the contention sense, then
      step "commit" [booking-clear] and release the winner.
    - booking-tied: step "tie" (the machine's named tie
      transition, guard booking-tied) into held, submit the
      envelope and leave it queued. No silent winner: the
      incumbent is untouched.
    - otherwise step "commit": booking-clear takes it active
      when clear, the machine's otherwise fallback takes it
      held when contended. Active -> submit + release_queued;
      held -> submit and leave queued.
- Preemption of an ACTIVE booking is an operator proposal
  (class "preemption") writing (1) the loser's unit with status
  "preempted" and (2) unit ``preemption/<loser-id>`` =
  {"winner", "winner_producer", "rank" (the winner's EFFECTIVE
  rank), "authority_sense", "at_seq"}, followed by stepping the
  loser's instance with event "preempt". ``at_seq`` is the seq
  of the last log entry before that preemption proposal was
  submitted -- the decision point, after the senses were
  published -- so an auditor can order grant < decision point <
  preemption execution from the log alone.
- ``disposal_pass`` runs after a winner commits: every HELD
  (queued) booking whose republished contention sense now
  lists the winner as a contender, and whose effective rank is
  rank-below the winner's, is disposed -- reject_queued, a
  preemption record write (record only: the loser's own write
  never executed, so there is no unit to rewrite), and the
  instance stepped "preempt" (held -> preempted). Equal rank
  (rank-below false) is left queued.

Known kernel friction the probe had to live with (see the
test module's report): release_queued / reject_queued take an
operator name but no reason -- the log records the fixed
strings "released-by-operator" / "rejected-by-operator", so
"released because the booking machine cleared it" and
"rejected because it was preempted by W" are NOT in the log;
the flow's reason survives only in the preemption record and
the machine transitions around the queue action.
"""
import copy

from jacquard import envelope_hash, make_envelope

import booking_flow
from authority_sense import install_words, publish_authority


def install(seq):
    """Install everything a live priority kernel needs: Probe
    A's lifecycles, guard words and booking machine, plus Probe
    C's rank words (which also registers both senses). Returns
    all verdicts; raises on any refusal."""
    verdicts = booking_flow.install(seq)
    verdicts["rank_words"] = install_words(seq)
    return verdicts


def _eval_word(seq, name, payload):
    stack, requests = seq.evaluate_word(name, "operator", [payload])
    if requests or len(stack) != 1:
        raise RuntimeError("word %s returned stack=%r requests=%r"
                           % (name, stack, requests))
    return stack[0]


def _unique_idem(seq, prefix):
    return "%s-%d" % (prefix, len(seq.log.entries))


# ---------------------------------------------------------- grants

def submit_grant(seq, producer, ceiling):
    """An operator grant: proposal (class "config") writing
    authority/<producer> = ceiling. Policy/1 allows it at once
    (write is not a protected effect, and the producer is the
    operator), so the grant is an execution in the log."""
    envelope = make_envelope(
        "operator", "proposal",
        {"class": "config",
         "requests": [{"verb": "write",
                       "args": ["authority/%s" % producer,
                                int(ceiling)]}]},
        ["write"], _unique_idem(seq, "probe-c-grant-" + producer))
    return seq.submit(envelope)


# ------------------------------------------------------- preemption

def _preemption_record(seq, loser_id, winner_booking, effective_rank,
                       authority_name):
    return {"winner": winner_booking["id"],
            "winner_producer": winner_booking["producer"],
            "rank": effective_rank,
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


def _preempt_active(seq, contender, winner_booking, effective_rank,
                    authority_name):
    """Preempt one ACTIVE contender: operator proposal writing
    the loser's unit as preempted plus the preemption record,
    the instance stepped "preempt", and -- defensively, per the
    brief -- a reject if the contender somehow still holds a
    queued proposal (an active contender's proposal already
    executed, so normally there is none)."""
    loser_id = contender["id"]
    box = winner_booking["box"]
    unit = "booking/%s/%s" % (box, loser_id)
    current = seq.state.units[unit]
    record = _preemption_record(seq, loser_id, winner_booking,
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
        _unique_idem(seq, "probe-c-preempt-" + loser_id))
    verdict = seq.submit(envelope)
    if verdict.get("outcome") != "allow":
        raise RuntimeError("preemption of %s refused: %r"
                           % (loser_id, verdict))
    _step_preempt(seq, loser_id, winner_booking)
    queued_pid = _queued_pid_for_unit(seq, unit)
    if queued_pid is not None:
        seq.reject_queued(queued_pid, "booking-flow")
    return record


def _dispose_queued(seq, loser_record, loser_pid, winner_booking):
    """Dispose of one HELD loser (see disposal_pass): reject its
    queued proposal so its write never executes, write the
    preemption record, step its instance "preempt"."""
    seq.reject_queued(loser_pid, "booking-flow")
    # The authority sense for the winner's producer, republished
    # so the record names a reading current at disposal time.
    authority_name = publish_authority(seq, winner_booking["producer"])
    record = _preemption_record(seq, loser_record["id"],
                                winner_booking,
                                winner_booking["rank"],
                                authority_name)
    envelope = make_envelope(
        "operator", "proposal",
        {"class": "preemption",
         "requests": [{"verb": "write",
                       "args": ["preemption/%s" % loser_record["id"],
                                record]}]},
        ["write"],
        _unique_idem(seq, "probe-c-dispose-" + loser_record["id"]))
    verdict = seq.submit(envelope)
    if verdict.get("outcome") != "allow":
        raise RuntimeError("disposal of %s refused: %r"
                           % (loser_record["id"], verdict))
    _step_preempt(seq, loser_record["id"], winner_booking)
    return record


# ------------------------------------------------------- live flow

def submit_live(seq, booking):
    """Submit one booking in live mode. `booking` carries the
    ASSERTED rank in "rank". Returns a routing report dict; the
    decisions themselves are the kernel's (senses, words,
    machine guards, policy queue)."""
    booking = dict(booking)
    asserted = booking["rank"]
    contention_name = booking_flow.publish_contention(seq, booking)
    authority_name = publish_authority(seq, booking["producer"])
    effective = _eval_word(seq, "effective-rank",
                           {"producer": booking["producer"],
                            "rank": asserted,
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
             {"verb": "write", "args": [unit, copy.deepcopy(record)]},
             {"verb": "notify",
              "args": ["booking-channel", booking["id"]]}]},
        ["write", "notify"],
        _unique_idem(seq, "probe-c-live-" + booking["id"]))
    proposal_id = envelope_hash(envelope)

    instance = "booking:%s" % booking["id"]
    if instance not in seq.state.machine_instances:
        seq.create_machine_instance("booking", instance)
    word_payload = {"sense_name": contention_name, "rank": effective}
    outranks = _eval_word(seq, "booking-outranks", word_payload)
    tied = _eval_word(seq, "booking-tied", word_payload)

    preempted = []
    if outranks:
        sense_value = seq.state.senses[contention_name]["value"]
        for contender in sense_value["contenders"]:
            _preempt_active(seq, contender, booking, effective,
                            authority_name)
            preempted.append(contender["id"])
        # Republish at the new decision point: now clear.
        contention_name = booking_flow.publish_contention(seq, booking)
        seq.step_machine(instance, "commit",
                         {**booking, "sense_name": contention_name,
                          "rank": effective})
    elif tied:
        seq.step_machine(instance, "tie",
                         {**booking, "sense_name": contention_name,
                          "rank": effective})
    else:
        seq.step_machine(instance, "commit",
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
    return {"booking_id": booking["id"], "proposal_id": proposal_id,
            "effective_rank": effective, "asserted_rank": asserted,
            "contention_sense": contention_name,
            "authority_sense": authority_name,
            "machine_state": state, "preempted": preempted,
            "verdict": verdict, "release": release,
            "record": record}


def disposal_pass(seq, winner_booking):
    """After `winner_booking` (a committed record, its "rank"
    the effective rank) commits, dispose of HELD bookings it now
    outranks. Returns the disposed booking ids, in queue order.
    Equal-rank held bookings are left queued."""
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
        if loser["id"] == winner_booking["id"]:
            continue
        name = booking_flow.publish_contention(seq, loser)
        value = seq.state.senses[name]["value"]
        if winner_booking["id"] not in [c["id"]
                                        for c in value["contenders"]]:
            continue
        below = _eval_word(seq, "rank-below",
                           {"rank": loser["rank"],
                            "limit": winner_booking["rank"]})
        if not below:
            continue  # tie or outranking holder: left queued
        _dispose_queued(seq, loser, proposal_id, winner_booking)
        disposed.append(loser["id"])
    return disposed
