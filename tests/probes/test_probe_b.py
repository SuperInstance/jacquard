"""Probe B (Phase 4, F2a): conditional starts -- "starts when X lands".

Scenarios S1-S8 from the probe brief, plus guard validation.
Every scenario uses a fresh Sequencer with the lifecycle
machines installed; the waiter proposal is a write to unit
"job/w1" with declared effects ["write"] (S4 gives the second
waiter "job/w2" so both executions are separately visible).

The verdict these scenarios support: the rung-2 encoding
(wait-condition as DATA on the queued proposal) runs every
scenario through the kernel's own queue/release/expire
machinery, and S7 reconstructs "why did this start?" from the
log alone -- while S6 demonstrates, by mechanical log scans,
that the rung-1 encoding (external watcher submits when the
condition fires) can answer neither "what are we waiting for?"
nor "why did this start?".

SUPERSESSION NOTE (spec 0.3, coordinator ruling, 2026-11-02):
this probe modelled the pump as a manual harness function
(wait_flow.pump) called explicitly after submissions.
Production internalised the pump into Sequencer exits in
the Phase 4 implementation slice (built on baseline
adb245e), exactly as the findings pinned -- so when a
scenario lands X via seq.submit, the waiter is already
released and executed before this probe's own pump(seq)
runs. The seven tests that assert the PROTOTYPE driver's
action lists are therefore pre-empted by production
legitimately; they are marked skip below (declared,
reasoned, visible -- not deleted) as the experiment
record. Every scenario's outcome assertions are preserved
and strengthened in tests/test_wait.py (23 tests) against
the production surface.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest  # noqa: E402

from jacquard import (Sequencer, envelope_hash, fold,  # noqa: E402
                      install_lifecycles, make_envelope)
from jacquard.state import Refusal  # noqa: E402
from wait_flow import (X_LANDED, define_guard, make_guard_defn,  # noqa: E402
                       pump, submit_waiting)

W1_VALUE = {"job": "w1"}


# ---------------------------------------------------------- helpers

def kernel(with_guard=True):
    seq = Sequencer()
    verdicts = install_lifecycles(seq)
    assert all(v["status"] == "accepted" for v in verdicts.values())
    if with_guard:
        verdict = define_guard(seq, X_LANDED)
        assert verdict["status"] == "accepted"
        assert verdict["computed_effects"] == []
    return seq


def waiter(producer="agent-a", unit="job/w1", value=None, idem="w1-1"):
    return make_envelope(
        producer, "proposal",
        {"requests": [{"verb": "write",
                       "args": [unit, W1_VALUE if value is None else value]}]},
        ["write"], idem)


def land(seq, unit="artifact/x", value=None, idem="land-1"):
    if value is None:
        value = {"status": "landed"}
    return seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": [unit, value]}]},
        ["write"], idem))


def far_deadline(seq):
    """A deadline no scenario's log growth can reach."""
    return len(seq.log.entries) + 1000


def executions_for(seq, proposal_id):
    return [e for e in seq.log.entries
            if e["kind"] == "execution"
            and e["body"].get("proposal_id") == proposal_id]


def decisions_for(seq, proposal_id):
    return [e for e in seq.log.entries
            if e["kind"] == "decision"
            and e["body"].get("proposal_id") == proposal_id]


def run_s1():
    """The S1 flow, shared by S1/S7/S8: queue a waiter on
    x-landed, land X, pump. Deterministic: same envelope ids,
    same order, every time it is run."""
    seq = kernel()
    env = waiter()
    pid = envelope_hash(env)
    verdict = submit_waiting(
        seq, env, {"guard": "x-landed",
                   "deadline_seq": far_deadline(seq)})
    assert verdict["outcome"] == "queue"
    landing = land(seq)
    assert landing["outcome"] == "allow"
    actions = pump(seq)
    return seq, pid, landing, actions


# ---------------------------------------------------------- S1

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s1_x_lands_releases_waiter():
    seq = kernel()
    env = waiter()
    pid = envelope_hash(env)
    wait = {"guard": "x-landed", "deadline_seq": far_deadline(seq)}
    verdict = submit_waiting(seq, env, wait)
    assert verdict["status"] == "decided"
    assert verdict["outcome"] == "queue"
    # Queued, with the wait spec carried on the decision entry.
    assert pid in seq.state.decision_queue
    queued = seq.state.decision_queue[pid]
    assert queued["outcome"] == "queued"
    assert queued["wait"] == wait
    assert queued["reasons"] == ["waiting:x-landed"]
    logged = [e for e in decisions_for(seq, pid)
              if e["body"].get("outcome") == "queued"]
    assert len(logged) == 1
    assert logged[0]["body"]["wait"] == wait
    # The proposal lifecycle stepped submit -> hold.
    assert seq.machine_instance_state(pid) == "tentative"
    assert executions_for(seq, pid) == []

    landing = land(seq)
    assert landing["outcome"] == "allow"

    assert pump(seq) == [("released", pid)]
    executions = executions_for(seq, pid)
    assert len(executions) == 1
    assert executions[0]["body"]["applied"] == [
        {"verb": "write", "args": ["job/w1", W1_VALUE]}]
    assert seq.state.units["job/w1"] == W1_VALUE
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- S2

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s2_x_never_lands_expires_by_deadline():
    seq = kernel()
    env = waiter()
    pid = envelope_hash(env)
    # deadline_seq is an absolute log-entry count (the literal
    # rung-2 spec): current entry count + 3. All log growth
    # counts toward it, including the waiter's own queueing
    # entries -- see the findings note in wait_flow's docstring.
    wait = {"guard": "x-landed",
            "deadline_seq": len(seq.log.entries) + 3}
    verdict = submit_waiting(seq, env, wait)
    assert verdict["outcome"] == "queue"
    assert pid in seq.state.decision_queue
    # Three unrelated entries; X never lands.
    for i in range(3):
        seq.checkpoint("unrelated-%d" % i)
    assert "artifact/x" not in seq.state.units

    assert pump(seq) == [("expired", pid)]
    assert executions_for(seq, pid) == []
    assert "job/w1" not in seq.state.units
    assert seq.state.decision_queue == {}
    # The expire path steps the proposal lifecycle to refuse.
    assert seq.machine_instance_state(pid) == "refused"


# ---------------------------------------------------------- S3a

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s3a_x_lands_twice_releases_exactly_once():
    seq, pid, _landing, actions = run_s1()
    assert actions == [("released", pid)]
    assert len(executions_for(seq, pid)) == 1
    # X lands again (a fresh write of the same unit).
    again = land(seq, value={"status": "landed", "note": "second"},
                 idem="land-2")
    assert again["outcome"] == "allow"
    assert pump(seq) == []
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- S3b

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s3b_lands_then_retracted_before_pump_does_not_start():
    """The semantics are STATE-BASED, not edge-based.

    The guard is re-evaluated against CURRENT committed state
    when the pump runs. A landing that was retracted (by a
    compensating write to the same unit) before that moment
    does not start the waiter -- an edge-based / event-based
    reading of "X landed at some point" would have started it.
    The waiter stays queued, and a later re-landing releases it.
    """
    seq = kernel()
    env = waiter()
    pid = envelope_hash(env)
    submit_waiting(seq, env, {"guard": "x-landed",
                              "deadline_seq": far_deadline(seq)})
    land(seq, idem="land-1")
    retract = land(seq, value={"status": "retracted"}, idem="land-2")
    assert retract["outcome"] == "allow"
    assert seq.state.units["artifact/x"] == {"status": "retracted"}

    # Guard reads current state: not landed -> no release, and
    # the deadline is far away -> no expiry either. Still queued.
    assert pump(seq) == []
    assert executions_for(seq, pid) == []
    assert pid in seq.state.decision_queue
    assert seq.machine_instance_state(pid) == "tentative"

    land(seq, idem="land-3")
    assert pump(seq) == [("released", pid)]
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == W1_VALUE


# ---------------------------------------------------------- S4

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s4_two_waiters_on_same_x_release_in_queue_order():
    seq = kernel()
    env_a = waiter(producer="agent-a", unit="job/w1",
                   value={"job": "w1"}, idem="w-a")
    env_b = waiter(producer="agent-b", unit="job/w2",
                   value={"job": "w2"}, idem="w-b")
    pid_a, pid_b = envelope_hash(env_a), envelope_hash(env_b)
    deadline = far_deadline(seq)
    assert submit_waiting(seq, env_a, {"guard": "x-landed",
                                       "deadline_seq": deadline}
                          )["outcome"] == "queue"
    assert submit_waiting(seq, env_b, {"guard": "x-landed",
                                       "deadline_seq": deadline}
                          )["outcome"] == "queue"
    assert list(seq.state.decision_queue) == [pid_a, pid_b]

    land(seq)
    assert pump(seq) == [("released", pid_a), ("released", pid_b)]
    assert len(executions_for(seq, pid_a)) == 1
    assert len(executions_for(seq, pid_b)) == 1
    assert seq.state.units["job/w1"] == {"job": "w1"}
    assert seq.state.units["job/w2"] == {"job": "w2"}
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- S5

def test_s5_condition_already_true_at_submission_is_immediate():
    seq = kernel()
    land(seq)
    assert "job/w1" not in seq.state.units
    env = waiter()
    pid = envelope_hash(env)
    before = len(seq.log.entries)
    result = submit_waiting(seq, env, {"guard": "x-landed",
                                       "deadline_seq": far_deadline(seq)})
    assert result["status"] == "immediate"
    # submit_waiting itself appended nothing and queued nothing.
    assert len(seq.log.entries) == before
    assert seq.state.decision_queue == {}
    # The caller submits through the normal path; it runs at once.
    verdict = seq.submit(env)
    assert verdict["outcome"] == "allow"
    assert verdict["proposal_id"] == pid
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == W1_VALUE
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- S6

def test_s6_rung1_watcher_leaves_no_audit_trail():
    """Rung 1, demonstrated: no wait spec anywhere. The pending
    intention lives only in an external watcher (here, this
    test), which polls committed state and submits the proposal
    when X lands. The outcome executes -- but the log alone
    cannot answer either audit question. Both failures are
    asserted by mechanical scans of the log, not by prose."""
    seq = kernel(with_guard=False)
    env = waiter(idem="w-rung1")
    pid = envelope_hash(env)

    landing = land(seq, idem="land-rung1")
    assert landing["outcome"] == "allow"
    # The log snapshot BEFORE the watcher submits anything.
    pre_submit = list(seq.log.entries)

    # (i) "What are we waiting for?" -- nothing in the log so
    # far names the pending intention: no entry references the
    # proposal, its target unit, or any wait.
    blobs = [json.dumps(e, sort_keys=True) for e in pre_submit]
    assert not any(pid in blob for blob in blobs)
    assert not any("job/w1" in blob for blob in blobs)
    assert not any("waiting:" in blob for blob in blobs)
    assert not any('"wait"' in blob for blob in blobs)

    # The external watcher (this test) polls state and submits.
    assert seq.state.units["artifact/x"] == {"status": "landed"}
    verdict = seq.submit(env)
    assert verdict["outcome"] == "allow"
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == W1_VALUE

    # (ii) "Why did this start?" -- the waiter's decision entry
    # carries no reference to X, to the landing, or to a wait:
    # no wait field, policy's own (empty) reasons, no "releases"
    # link, and neither the landing entry's hash nor the unit
    # name appears anywhere in it.
    landing_entry = executions_for(seq, landing["proposal_id"])[0]
    waiter_decisions = decisions_for(seq, pid)
    assert waiter_decisions
    for entry in waiter_decisions:
        body = entry["body"]
        assert "wait" not in body
        assert "releases" not in body
        assert body["reasons"] == []
        blob = json.dumps(body, sort_keys=True)
        assert "artifact/x" not in blob
        assert "landed" not in blob
        assert landing_entry["hash"] not in blob


# ---------------------------------------------------------- S7

@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_s7_rung2_audit_reconstructed_from_log_alone():
    """The rung-2 contrast to S6: from the log alone, why the
    waiter started is a chain of three mechanical facts."""
    seq, pid, landing, actions = run_s1()
    assert actions == [("released", pid)]

    # 1. The queueing decision names the guard that was awaited.
    queued = [e for e in decisions_for(seq, pid)
              if e["body"].get("outcome") == "queued"]
    assert len(queued) == 1
    assert queued[0]["body"]["wait"]["guard"] == "x-landed"
    assert queued[0]["body"]["reasons"] == ["waiting:x-landed"]

    # 2+3. The landing's execution precedes the release
    # decision, and the release decision names the proposal it
    # releases (its "releases" field) -- landing caused release.
    landing_exec = executions_for(seq, landing["proposal_id"])
    assert len(landing_exec) == 1
    releases = [e for e in decisions_for(seq, pid)
                if e["body"].get("releases") == pid]
    assert len(releases) == 1
    assert landing_exec[0]["seq"] < releases[0]["seq"]
    assert queued[0]["seq"] < releases[0]["seq"]
    # And the waiter's own execution follows the release.
    waiter_exec = executions_for(seq, pid)
    assert len(waiter_exec) == 1
    assert releases[0]["seq"] < waiter_exec[0]["seq"]


# ---------------------------------------------------------- S8

def test_s8_determinism_fold_and_replay():
    seq, pid, _landing, _actions = run_s1()
    # Fold of the log reproduces the sequencer's live state.
    folded = fold(seq.log.entries)
    assert folded.state_hash() == seq.state.state_hash()
    # A fresh sequencer replaying the same submissions in the
    # same order reaches the identical state -- and, stronger,
    # the identical hash-chained log.
    seq2, pid2, _landing2, _actions2 = run_s1()
    assert pid2 == pid
    assert seq2.state.state_hash() == seq.state.state_hash()
    assert [e["hash"] for e in seq2.log.entries] == \
        [e["hash"] for e in seq.log.entries]


# ---------------------------------------------------------- guard validation

def test_guard_that_does_not_exist_is_refused_before_any_append():
    seq = kernel(with_guard=False)
    env = waiter()
    pid = envelope_hash(env)
    before = len(seq.log.entries)
    with pytest.raises(Refusal) as caught:
        submit_waiting(seq, env, {"guard": "no-such-word",
                                  "deadline_seq": far_deadline(seq)})
    assert caught.value.name == "SPEC"
    assert len(seq.log.entries) == before
    assert pid not in seq.state.decision_queue
    assert seq.machine_instance_state(pid) is None


def test_guard_with_computed_effects_is_refused_before_any_append():
    seq = kernel()
    impure = {"name": "impure-guard",
              "signature": {"ins": ["map"], "outs": ["bool"]},
              "body": ["dispatch", {"lit": True}],
              "examples": [{"args": [{"job": "x"}], "expect": [True],
                            "requests": ["dispatch"]}]}
    verdict = define_guard(seq, impure)
    assert verdict["status"] == "accepted"
    assert verdict["computed_effects"] == ["dispatch"]
    env = waiter()
    pid = envelope_hash(env)
    before = len(seq.log.entries)
    with pytest.raises(Refusal) as caught:
        submit_waiting(seq, env, {"guard": "impure-guard",
                                  "deadline_seq": far_deadline(seq)})
    assert caught.value.name == "SPEC"
    assert len(seq.log.entries) == before
    assert pid not in seq.state.decision_queue


def test_guard_with_wrong_signature_is_refused_before_any_append():
    seq = kernel()
    double = {"name": "double",
              "signature": {"ins": ["int"], "outs": ["int"]},
              "body": ["dup", "add"],
              "examples": [{"args": [2], "expect": [4]}]}
    verdict = define_guard(seq, double)
    assert verdict["status"] == "accepted"
    assert verdict["computed_effects"] == []
    env = waiter()
    before = len(seq.log.entries)
    with pytest.raises(Refusal) as caught:
        submit_waiting(seq, env, {"guard": "double",
                                  "deadline_seq": far_deadline(seq)})
    assert caught.value.name == "FIELD"
    assert len(seq.log.entries) == before


@pytest.mark.skip(reason="superseded by tests/test_wait.py: production internalised the pump into Sequencer exits, pre-empting the prototype driver's action list (coordinator ruling, spec 0.3)")
def test_parameterised_guard_for_another_unit():
    """One word per artefact: the same construction defines
    y-landed for "artifact/y", and a waiter on it is not
    released by X landing -- only by Y."""
    seq = kernel()
    verdict = define_guard(seq, make_guard_defn("artifact/y"))
    assert verdict["status"] == "accepted"
    env = waiter(idem="w-y1")
    pid = envelope_hash(env)
    submit_waiting(seq, env, {"guard": "y-landed",
                              "deadline_seq": far_deadline(seq)})
    land(seq, idem="land-x-only")
    assert pump(seq) == []
    assert pid in seq.state.decision_queue
    land(seq, unit="artifact/y", idem="land-y")
    assert pump(seq) == [("released", pid)]
    assert len(executions_for(seq, pid)) == 1
