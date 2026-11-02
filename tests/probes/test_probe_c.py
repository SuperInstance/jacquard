"""Probe C (Phase 4, F2b): authority priority over contention.

Scenarios C1-C6 from the staged brief, on fresh kernels.
Decomposition under test: rank is DATA (rung 2 -- an asserted
rank on the booking, an operator grant writing
authority/<producer>), override is MACHINE (rung 3 -- the
booking machine's "preempt" transition on the loser, plus a
preemption record), and the rank predicates are a SENSE plus
words (rung 4 -- the authority sense counts OPERATOR executions
only; effective-rank clamps the asserted rank to the granted
ceiling by dictionary evaluation). Contention itself is Probe
A's winner, reused unmodified.

Report notes (the brief asks for the precise kernel changes
the implementation slice would need):

- reject_queued / release_queued take an operator name but no
  reason parameter: the queue decisions in the log carry the
  kernel's fixed reasons ("rejected-by-operator" /
  "released-by-operator"). A preemption disposal and an
  ordinary operator rejection are therefore indistinguishable
  in the decision entry itself; the slice should add an
  optional reason parameter to both, recorded on the decision
  entry. In this probe the reason survives in the preemption
  record and the booking machine's transitions.
- Preemption here is OPERATOR PROPOSALS (class "preemption")
  submitted by the flow, not kernel-generated writes. Trade-
  off: everything is an ordinary logged envelope -- auditable,
  policy-gated, replayable with zero kernel changes -- at the
  cost of the flow being trusted to submit them; a kernel-
  generated path would need a new entry path in the sequencer
  and would bypass the policy gate the proposals pass through.
  The probe's evidence favours proposals: C1's audit replays
  the whole override from ordinary entries alone.
- What the probe had to fake: nothing in the decision path.
  Two honest approximations: (1) the preemption record's
  at_seq is stamped by the flow (the last log seq before the
  preemption proposal was submitted) because no kernel field
  carries a decision-point seq -- a slice could have the
  sequencer stamp it; (2) the live booking record carries an
  extra "asserted_rank" field so a held proposal's queued
  decision entry shows what was asserted alongside the
  effective rank it would commit with -- envelope data, no
  kernel change, but the slice should name the field in spec.
- C3's tie outcome, honestly read: the brief's charter asks
  for "rank tie -> named refusal, no silent winner". What the
  probe produces is a NAMED outcome -- a transition entry with
  event "tie" and guard "booking-tied", the contender visible
  in the published contention sense, the challenger held and
  its proposal queued for a batched operator decision -- but
  it is not a REFUSAL: the challenger is not denied, it waits
  in the decision queue for a batched operator decision, and
  no preemption path was taken against the incumbent.
  Whether "queued +
  named tie transition" satisfies "named refusal" is a spec
  call; this probe's recommendation is that the findings ask
  for a spec-level refusal/outcome name for the tie (e.g. the
  decision-queue outcome stays queued, but the machine outcome
  vocabulary gains a named "tied" reading) rather than the
  probe inventing one. The tests below pin the behaviour that
  exists, not the name that should.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from jacquard import Sequencer, make_envelope  # noqa: E402

import priority_flow  # noqa: E402
from authority_sense import publish_authority  # noqa: E402


# ---------------------------------------------------------- helpers

def kernel():
    seq = Sequencer()
    priority_flow.install(seq)
    return seq


def booking(id_, producer, start, end, rank=0, seat="gpu", box="thor"):
    return {"id": id_, "box": box, "producer": producer,
            "seat": seat, "start": start, "end": end,
            "checkby": None, "status": "active", "rank": rank}


def grant(seq, producer, ceiling):
    verdict = priority_flow.submit_grant(seq, producer, ceiling)
    assert verdict["outcome"] == "allow", verdict
    return verdict


def executions_for(seq, proposal_id):
    return [e for e in seq.log.entries
            if e["kind"] == "execution"
            and e["body"].get("proposal_id") == proposal_id]


def transitions_for(seq, instance, event=None):
    return [e for e in seq.log.entries
            if e["kind"] == "transition"
            and e["body"].get("instance") == instance
            and (event is None or e["body"].get("event") == event)]


def audit_preemption(entries, loser_id):
    """Reconstruct an override FROM THE LOG ALONE: who won,
    whose rank, and where the authority for it was granted.

    Finds the preemption record write for `loser_id`, then the
    grant: the latest OPERATOR execution writing
    authority/<winner_producer> BEFORE the preemption execution.
    Returns {"winner", "winner_producer", "rank", "grant_seq"}.
    """
    record = None
    record_seq = None
    for entry in entries:
        if entry["kind"] != "execution":
            continue
        for applied in entry["body"].get("applied", []):
            if applied.get("verb") == "write" \
                    and applied["args"][0] == "preemption/%s" % loser_id:
                record = applied["args"][1]
                record_seq = entry["seq"]
    assert record is not None, "no preemption record for %s" % loser_id
    grant_unit = "authority/%s" % record["winner_producer"]
    grant_seq = None
    for entry in entries:
        if entry["seq"] >= record_seq:
            break
        if entry["kind"] != "execution":
            continue
        if entry["body"].get("producer") != "operator":
            continue
        for applied in entry["body"].get("applied", []):
            if applied.get("verb") == "write" \
                    and applied["args"][0] == grant_unit:
                grant_seq = entry["seq"]
    assert grant_seq is not None, "no grant precedes the preemption"
    return {"winner": record["winner"],
            "winner_producer": record["winner_producer"],
            "rank": record["rank"],
            "grant_seq": grant_seq}


# ---------------------------------------------------------- C1

def test_c1_override_of_active_booking_with_audit_replay(capsys):
    seq = kernel()
    grant(seq, "captain", 5)
    x = priority_flow.submit_live(seq, booking("X", "lane-a", 100, 200))
    assert x["machine_state"] == "active"
    assert x["effective_rank"] == 0
    assert seq.state.units["booking/thor/X"]["status"] == "active"

    w = priority_flow.submit_live(
        seq, booking("W", "captain", 150, 250, rank=5))
    assert w["preempted"] == ["X"]
    assert w["machine_state"] == "active"
    assert w["effective_rank"] == 5

    # The loser: unit rewritten preempted, instance preempted,
    # with a taken "preempt" transition naming the winner.
    assert seq.state.units["booking/thor/X"]["status"] == "preempted"
    assert seq.machine_instance_state("booking:X") == "preempted"
    steps = [e for e in transitions_for(seq, "booking:X", "preempt")
             if e["body"]["outcome"] == "taken"]
    assert len(steps) == 1
    assert steps[0]["body"]["to"] == "preempted"

    # The preemption record, exactly as specified.
    record = seq.state.units["preemption/X"]
    assert record["winner"] == "W"
    assert record["winner_producer"] == "captain"
    assert record["rank"] == 5
    assert record["authority_sense"] == "authority:captain"
    assert isinstance(record["at_seq"], int)

    # The winner committed with the EFFECTIVE rank stored.
    winner = seq.state.units["booking/thor/W"]
    assert winner["status"] == "active"
    assert winner["rank"] == 5

    # Audit replay from the log alone, and the ordering proof:
    # grant precedes the preemption; no override without its
    # authority entry before it.
    audit = audit_preemption(seq.log.entries, "X")
    grant_entry = seq.log.entries[audit["grant_seq"]]
    assert grant_entry["kind"] == "execution"
    assert grant_entry["body"]["producer"] == "operator"
    assert {"verb": "write", "args": ["authority/captain", 5]} in \
        grant_entry["body"]["applied"]
    preemption_seq = next(
        e["seq"] for e in seq.log.entries
        if e["kind"] == "execution"
        and any(a.get("verb") == "write"
                and a["args"][0] == "preemption/X"
                for a in e["body"].get("applied", [])))
    assert audit["grant_seq"] < record["at_seq"] < preemption_seq
    assert audit == {"winner": "W", "winner_producer": "captain",
                     "rank": 5, "grant_seq": audit["grant_seq"]}
    print("C1 AUDIT:", audit)


# ---------------------------------------------------------- C2

def test_c2_override_of_queued_booking_disposes_loser():
    seq = kernel()
    grant(seq, "captain", 5)
    priority_flow.submit_live(seq, booking("X", "lane-a", 100, 200))
    loser = priority_flow.submit_live(
        seq, booking("L", "lane-b", 150, 250))
    # Contended at equal rank 0: held by the machine, queued by
    # policy, its write never executed.
    assert loser["machine_state"] == "held"
    assert loser["proposal_id"] in seq.state.decision_queue
    assert "booking/thor/L" not in seq.state.units
    assert executions_for(seq, loser["proposal_id"]) == []

    w = priority_flow.submit_live(
        seq, booking("W", "captain", 150, 250, rank=5))
    assert w["preempted"] == ["X"]       # the active path
    assert w["machine_state"] == "active"

    winner_record = seq.state.units["booking/thor/W"]
    disposed = priority_flow.disposal_pass(seq, winner_record)
    assert disposed == ["L"]

    # L disposed: rejected from the queue, preemption record
    # written, instance preempted -- and its write STILL never
    # executed (no execution entry for L's proposal at all).
    assert loser["proposal_id"] not in seq.state.decision_queue
    assert executions_for(seq, loser["proposal_id"]) == []
    assert "booking/thor/L" not in seq.state.units
    record = seq.state.units["preemption/L"]
    assert record["winner"] == "W"
    assert record["winner_producer"] == "captain"
    assert record["rank"] == 5
    assert seq.machine_instance_state("booking:L") == "preempted"
    rejections = [e for e in seq.log.entries
                  if e["kind"] == "decision"
                  and e["body"].get("rejects") == loser["proposal_id"]]
    assert len(rejections) == 1
    assert rejections[0]["body"]["outcome"] == "deny"


# ---------------------------------------------------------- C3

def test_c3_rank_tie_named_no_silent_winner():
    seq = kernel()
    grant(seq, "captain", 5)
    grant(seq, "captain2", 5)
    x = priority_flow.submit_live(
        seq, booking("X", "captain", 100, 200, rank=5))
    assert x["machine_state"] == "active"
    assert seq.state.units["booking/thor/X"]["rank"] == 5

    w = priority_flow.submit_live(
        seq, booking("W", "captain2", 150, 250, rank=5))
    # Tied at 5: challenger held via the named tie transition
    # and queued; incumbent untouched; nobody silently won.
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    assert w["proposal_id"] in seq.state.decision_queue
    assert executions_for(seq, w["proposal_id"]) == []
    assert "booking/thor/W" not in seq.state.units
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units
    assert seq.machine_instance_state("booking:X") == "active"
    ties = [e for e in transitions_for(seq, "booking:W", "tie")
            if e["body"]["outcome"] == "taken"]
    assert len(ties) == 1
    assert ties[0]["body"]["guard"] == "booking-tied"
    assert ties[0]["body"]["to"] == "held"
    # The equal-rank contender is visible in the published
    # contention sense the guard read.
    value = seq.state.senses[w["contention_sense"]]["value"]
    assert [c["id"] for c in value["contenders"]] == ["X"]
    assert value["max_rank"] == 5


# ---------------------------------------------------------- C4

def test_c4_unrecognised_rank_is_effective_zero():
    seq = kernel()
    priority_flow.submit_live(seq, booking("X", "lane-a", 100, 200))
    w = priority_flow.submit_live(
        seq, booking("W", "mallory", 150, 250, rank=9))
    # No grant: the authority sense says ceiling null, the
    # effective rank is 0, so this is ordinary contention --
    # held via otherwise, queued, no preemption.
    assert w["effective_rank"] == 0
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    sense = seq.state.senses["authority:mallory"]["value"]
    assert sense == {"ceiling": None, "grants": 0}
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units
    assert "booking/thor/W" not in seq.state.units
    assert executions_for(seq, w["proposal_id"]) == []
    # The asserted 9 is visible in her (queued) proposal body;
    # the rank it would commit with is the effective 0.
    queued = seq.state.decision_queue[w["proposal_id"]]
    write = next(r for r in queued["requests"] if r["verb"] == "write")
    assert write["args"][1]["asserted_rank"] == 9
    assert write["args"][1]["rank"] == 0
    # And the words themselves, evaluated directly.
    stack, _ = seq.evaluate_word(
        "effective-rank", "operator",
        [{"producer": "mallory", "rank": 9,
          "sense_name": "authority:mallory"}])
    assert stack == [0]
    stack, _ = seq.evaluate_word(
        "rank-granted", "operator",
        [{"producer": "mallory", "rank": 9,
          "sense_name": "authority:mallory"}])
    assert stack == [False]


# ---------------------------------------------------------- C5

def test_c5_self_grant_attack_is_inert():
    seq = kernel()
    priority_flow.submit_live(seq, booking("X", "lane-a", 100, 200))
    # Mallory writes her own authority unit. Policy/1 allows the
    # write -- assert it LANDS in units. That is not the hole:
    # the authority sense counts operator executions only.
    verdict = seq.submit(make_envelope(
        "mallory", "proposal",
        {"class": "config",
         "requests": [{"verb": "write",
                       "args": ["authority/mallory", 99]}]},
        ["write"], "probe-c-selfgrant-1"))
    assert verdict["outcome"] == "allow", verdict
    assert seq.state.units["authority/mallory"] == 99

    name = publish_authority(seq, "mallory")
    assert name == "authority:mallory"
    # BOTH halves of the finding: the unit landed AND the
    # ceiling stayed null.
    assert seq.state.units["authority/mallory"] == 99
    assert seq.state.senses[name]["value"] == {"ceiling": None,
                                               "grants": 0}

    # Her rank-9 override attempt fails exactly as in C4.
    w = priority_flow.submit_live(
        seq, booking("W", "mallory", 150, 250, rank=9))
    assert w["effective_rank"] == 0
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units
    assert seq.state.senses["authority:mallory"]["value"][
        "ceiling"] is None


# ---------------------------------------------------------- C6

def test_c6_word_level_clamp():
    seq = kernel()
    grant(seq, "captain", 2)
    publish_authority(seq, "captain")

    def effective(rank, producer="captain"):
        stack, _ = seq.evaluate_word(
            "effective-rank", "operator",
            [{"producer": producer, "rank": rank,
              "sense_name": "authority:%s" % producer}])
        return stack[0]

    def granted(rank, producer="captain"):
        stack, _ = seq.evaluate_word(
            "rank-granted", "operator",
            [{"producer": producer, "rank": rank,
              "sense_name": "authority:%s" % producer}])
        return stack[0]

    assert effective(5) == 2     # clamped to the ceiling
    assert effective(2) == 2
    assert effective(1) == 1
    assert granted(2) is True
    assert granted(5) is False
    publish_authority(seq, "mallory")
    assert effective(9, "mallory") == 0
    assert granted(9, "mallory") is False


def test_c6_clamped_rank_does_not_preempt_higher():
    seq = kernel()
    grant(seq, "captain", 2)
    grant(seq, "chief", 3)
    x = priority_flow.submit_live(
        seq, booking("X", "chief", 100, 200, rank=3))
    assert x["effective_rank"] == 3
    assert seq.state.units["booking/thor/X"]["rank"] == 3

    w = priority_flow.submit_live(
        seq, booking("W", "captain", 150, 250, rank=5))
    # Asserted 5, effective 2, contender rank 3: no preemption,
    # ordinary held.
    assert w["effective_rank"] == 2
    assert w["preempted"] == []
    assert w["machine_state"] == "held"
    assert w["proposal_id"] in seq.state.decision_queue
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units


def test_c6_clamped_rank_preempts_lower():
    seq = kernel()
    grant(seq, "captain", 2)
    grant(seq, "lane-y", 1)
    y = priority_flow.submit_live(
        seq, booking("Y", "lane-y", 100, 200, rank=1))
    assert y["effective_rank"] == 1

    w = priority_flow.submit_live(
        seq, booking("W", "captain", 150, 250, rank=5))
    # Effective 2 > 1: preempts -- with rank 2 recorded, never
    # the asserted 5.
    assert w["effective_rank"] == 2
    assert w["preempted"] == ["Y"]
    assert w["machine_state"] == "active"
    assert seq.state.units["booking/thor/Y"]["status"] == "preempted"
    assert seq.state.units["preemption/Y"]["rank"] == 2
    winner = seq.state.units["booking/thor/W"]
    assert winner["rank"] == 2
    assert winner["asserted_rank"] == 5
