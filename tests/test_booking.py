"""The booking profile (spec 0.3, section 11.4): Probe C's
scenarios C1-C6 ported to the production module, Probe A's
essentials against the production contention sense, and the
fail-closed unclassified-seat behaviour the findings add.
Nothing here registers a probe sense: the senses under test
are the kernel's built-ins.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import (BookingFlow, Log, Sequencer, compute_sense,  # noqa: E402
                      install_booking, make_envelope, publish_authority)
from jacquard import senses as _senses_module  # noqa: E402
from jacquard.booking import publish_contention  # noqa: E402
from jacquard.state import Refusal, State  # noqa: E402


@pytest.fixture(autouse=True)
def _production_senses():
    """The probe modules register their own candidate senses
    into SENSES at runtime (the registry hazard the slice brief
    names). Production tests re-register the production
    functions first, per the brief."""
    _senses_module.SENSES["contention"] = \
        _senses_module._contention
    _senses_module.SENSES["authority"] = _senses_module._authority


# ---------------------------------------------------------- helpers

def kernel():
    seq = Sequencer()
    install_booking(seq)
    return seq, BookingFlow(seq)


def booking(id_, producer="lane-a", start=1000, end=1200, rank=0,
            seat="gpu", box="thor", status="active"):
    return {"id": id_, "box": box, "producer": producer,
            "seat": seat, "start": start, "end": end,
            "checkby": None, "status": status, "rank": rank}


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
    """Reconstruct an override FROM THE LOG ALONE (probe C1)."""
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

def test_c1_override_of_active_booking_with_audit_replay():
    seq, flow = kernel()
    assert flow.grant("captain", 5)["outcome"] == "allow"
    x = flow.submit_live(booking("X", "lane-a", 100, 200))
    assert x["machine_state"] == "active"
    assert x["effective_rank"] == 0

    w = flow.submit_live(booking("W", "captain", 150, 250, rank=5))
    assert w["preempted"] == ["X"]
    assert w["machine_state"] == "active"
    assert w["effective_rank"] == 5

    assert seq.state.units["booking/thor/X"]["status"] == "preempted"
    assert seq.machine_instance_state("booking:X") == "preempted"
    steps = [e for e in transitions_for(seq, "booking:X", "preempt")
             if e["body"]["outcome"] == "taken"]
    assert len(steps) == 1

    record = seq.state.units["preemption/X"]
    assert record["winner"] == "W"
    assert record["winner_producer"] == "captain"
    assert record["rank"] == 5
    assert record["authority_sense"] == "authority:captain"
    assert isinstance(record["at_seq"], int)

    winner = seq.state.units["booking/thor/W"]
    assert winner["status"] == "active"
    assert winner["rank"] == 5
    assert winner["asserted_rank"] == 5

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


# ---------------------------------------------------------- C2

def test_c2_override_of_queued_booking_disposes_loser():
    seq, flow = kernel()
    flow.grant("captain", 5)
    flow.submit_live(booking("X", "lane-a", 100, 200))
    loser = flow.submit_live(booking("L", "lane-b", 150, 250))
    assert loser["machine_state"] == "held"
    assert loser["proposal_id"] in seq.state.decision_queue
    assert "booking/thor/L" not in seq.state.units
    assert executions_for(seq, loser["proposal_id"]) == []

    w = flow.submit_live(booking("W", "captain", 150, 250, rank=5))
    assert w["preempted"] == ["X"]
    assert w["machine_state"] == "active"

    winner_record = seq.state.units["booking/thor/W"]
    assert flow.dispose(winner_record) == ["L"]

    assert loser["proposal_id"] not in seq.state.decision_queue
    assert executions_for(seq, loser["proposal_id"]) == []
    assert "booking/thor/L" not in seq.state.units
    record = seq.state.units["preemption/L"]
    assert record["winner"] == "W"
    assert record["rank"] == 5
    assert seq.machine_instance_state("booking:L") == "preempted"
    rejections = [e for e in seq.log.entries
                  if e["kind"] == "decision"
                  and e["body"].get("rejects") == loser["proposal_id"]]
    assert len(rejections) == 1
    assert rejections[0]["body"]["outcome"] == "deny"
    # The production reason parameter carries WHY, in the entry.
    assert rejections[0]["body"]["reasons"] == ["preempted-by:W"]


# ---------------------------------------------------------- C3

def test_c3_rank_tie_named_no_silent_winner():
    seq, flow = kernel()
    flow.grant("captain", 5)
    flow.grant("captain2", 5)
    x = flow.submit_live(booking("X", "captain", 100, 200, rank=5))
    assert x["machine_state"] == "active"

    w = flow.submit_live(booking("W", "captain2", 150, 250, rank=5))
    # Tied at 5: challenger held via the named tie transition and
    # queued; the incumbent holds the interval, untouched.
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    assert w["proposal_id"] in seq.state.decision_queue
    assert executions_for(seq, w["proposal_id"]) == []
    assert "booking/thor/W" not in seq.state.units
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units
    ties = [e for e in transitions_for(seq, "booking:W", "tie")
            if e["body"]["outcome"] == "taken"]
    assert len(ties) == 1
    assert ties[0]["body"]["guard"] == "booking-tied"
    assert ties[0]["body"]["to"] == "held"
    value = seq.state.senses[w["contention_sense"]]["value"]
    assert [c["id"] for c in value["contenders"]] == ["X"]
    assert value["max_rank"] == 5


# ---------------------------------------------------------- C4/C5

def test_c4_unrecognised_rank_is_effective_zero():
    seq, flow = kernel()
    flow.submit_live(booking("X", "lane-a", 100, 200))
    w = flow.submit_live(booking("W", "mallory", 150, 250, rank=9))
    assert w["effective_rank"] == 0
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    sense = seq.state.senses["authority:mallory"]["value"]
    assert sense == {"ceiling": None, "grants": 0}
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units
    queued = seq.state.decision_queue[w["proposal_id"]]
    write = next(r for r in queued["requests"] if r["verb"] == "write")
    assert write["args"][1]["asserted_rank"] == 9
    assert write["args"][1]["rank"] == 0
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


def test_c5_self_grant_attack_is_inert():
    seq, flow = kernel()
    flow.submit_live(booking("X", "lane-a", 100, 200))
    verdict = seq.submit(make_envelope(
        "mallory", "proposal",
        {"class": "config",
         "requests": [{"verb": "write",
                       "args": ["authority/mallory", 99]}]},
        ["write"], "selfgrant-1"))
    assert verdict["outcome"] == "allow", verdict
    assert seq.state.units["authority/mallory"] == 99

    name = publish_authority(seq, "mallory")
    assert seq.state.units["authority/mallory"] == 99
    assert seq.state.senses[name]["value"] == {"ceiling": None,
                                               "grants": 0}
    w = flow.submit_live(booking("W", "mallory", 150, 250, rank=9))
    assert w["effective_rank"] == 0
    assert w["machine_state"] == "held"
    assert w["preempted"] == []
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units


# ---------------------------------------------------------- C6

def test_c6_word_level_clamp_and_last_wins():
    seq, flow = kernel()
    flow.grant("captain", 2)
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

    # A later LOWER grant is a downward revocation (last-wins).
    flow.grant("captain", 5)
    flow.grant("captain", 1)
    reading = compute_sense("authority:captain", seq.log.entries,
                            seq.state)
    assert reading["value"] == {"ceiling": 1, "grants": 3}


def test_c6_clamped_rank_does_not_preempt_higher():
    seq, flow = kernel()
    flow.grant("captain", 2)
    flow.grant("chief", 3)
    x = flow.submit_live(booking("X", "chief", 100, 200, rank=3))
    assert x["effective_rank"] == 3
    w = flow.submit_live(booking("W", "captain", 150, 250, rank=5))
    assert w["effective_rank"] == 2
    assert w["preempted"] == []
    assert w["machine_state"] == "held"
    assert seq.state.units["booking/thor/X"]["status"] == "active"
    assert "preemption/X" not in seq.state.units


def test_c6_clamped_rank_preempts_lower():
    seq, flow = kernel()
    flow.grant("captain", 2)
    flow.grant("lane-y", 1)
    y = flow.submit_live(booking("Y", "lane-y", 100, 200, rank=1))
    assert y["effective_rank"] == 1
    w = flow.submit_live(booking("W", "captain", 150, 250, rank=5))
    assert w["effective_rank"] == 2
    assert w["preempted"] == ["Y"]
    assert w["machine_state"] == "active"
    assert seq.state.units["booking/thor/Y"]["status"] == "preempted"
    assert seq.state.units["preemption/Y"]["rank"] == 2
    winner = seq.state.units["booking/thor/W"]
    assert winner["rank"] == 2
    assert winner["asserted_rank"] == 5


# -------------------------------------------- contention battery

def _state_with(rows):
    state = State()
    for row in rows:
        state.units["booking/%s/%s" % (row["box"], row["id"])] = row
    return state


def _contend(rows, subject="thor/gpu/1100/1300/lane-b/cand"):
    return compute_sense("contention:" + subject, [], _state_with(rows))


def test_contention_touching_endpoints_do_not_contend():
    rows = [booking("o1", start=900, end=1100),
            booking("o2", start=1300, end=1500)]
    assert _contend(rows)["value"]["count"] == 0


def test_contention_contained_and_containing_contend():
    rows = [booking("inside", start=1150, end=1200),
            booking("outside", start=1000, end=1400)]
    value = _contend(rows)["value"]
    assert [c["id"] for c in value["contenders"]] == \
        ["inside", "outside"]
    assert value["count"] == 2
    assert value["max_rank"] == 0
    assert value["top_id"] == "inside"


def test_contention_checkby_expiry():
    dead = booking("dead", start=1000, end=1200)
    dead["checkby"] = 1000          # check-by before candidate start
    alive = booking("alive", start=1000, end=1200)
    alive["checkby"] = 1100         # check-by == candidate start
    value = _contend([dead, alive])["value"]
    assert [c["id"] for c in value["contenders"]] == ["alive"]


def test_contention_renewal_and_id_exclusion():
    renewal = booking("ren", producer="lane-b")     # same producer
    same_id = booking("cand", producer="lane-a")    # candidate's id
    assert _contend([renewal, same_id])["value"]["count"] == 0


def test_contention_inert_statuses_and_seat_rules():
    rows = [booking("done1", status="done"),
            booking("can1", status="cancelled"),
            booking("det", seat="detached"),        # same seat, not exclusive
            booking("boxseat", seat="box", start=2000, end=2200)]
    # Only "boxseat" could contend by seat, and it does not overlap.
    assert _contend(rows)["value"]["count"] == 0
    rows[-1] = booking("boxseat", seat="box", start=1000, end=1200)
    value = _contend(rows)["value"]
    assert [c["id"] for c in value["contenders"]] == ["boxseat"]


# -------------------------------------------- unclassified seats

def test_unclassified_seat_reported_and_fails_closed():
    seq, flow = kernel()
    cand = booking("Z", "lane-a", 100, 200, seat="zcod")
    name = publish_contention(seq, cand)
    value = seq.state.senses[name]["value"]
    assert value["unclassified"] == ["zcod"]
    assert value["count"] == 0
    # booking-clear requires the unclassified list empty.
    stack, _ = seq.evaluate_word("booking-clear", "operator",
                                 [{"sense_name": name}])
    assert stack == [False]
    # So the flow holds the booking for a human.
    result = flow.submit_live(cand)
    assert result["machine_state"] == "held"
    assert result["proposal_id"] in seq.state.decision_queue
    assert "booking/thor/Z" not in seq.state.units


def test_classified_candidate_clears():
    seq, flow = kernel()
    cand = booking("Z", "lane-a", 100, 200, seat="gpu")
    name = publish_contention(seq, cand)
    assert seq.state.senses[name]["value"]["unclassified"] == []
    stack, _ = seq.evaluate_word("booking-clear", "operator",
                                 [{"sense_name": name}])
    assert stack == [True]


def test_slash_in_candidate_field_refused_by_name():
    seq, _flow = kernel()
    cand = booking("Z", "lane-a", 100, 200)
    cand["box"] = "th/or"
    with pytest.raises(Refusal) as caught:
        publish_contention(seq, cand)
    assert caught.value.name == "FIELD"


# -------------------------------------------- CLI tie annotation

def test_cli_annotates_authority_tie(tmp_path):
    log = tmp_path / "kernel.jsonl"
    seq = Sequencer(Log(str(log)))
    install_booking(seq)
    flow = BookingFlow(seq)
    flow.grant("captain", 5)
    flow.grant("captain2", 5)
    flow.submit_live(booking("X", "captain", 100, 200, rank=5))
    tied = flow.submit_live(booking("W", "captain2", 150, 250,
                                    rank=5))
    assert tied["machine_state"] == "held"
    jq = os.path.join(os.path.dirname(__file__), "..",
                      "tools", "jq.py")
    proc = subprocess.run(
        [sys.executable, jq, "--log", str(log), "queue"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert tied["proposal_id"] in proc.stdout
    assert "authority tie" in proc.stdout
