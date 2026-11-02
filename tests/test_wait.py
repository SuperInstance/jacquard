"""Wait support (spec 0.3, section 7): conditional starts as a
field on the proposal body, re-evaluated by the sequencer's
pump after every appending call.

These are Probe B's scenarios ported to the production surface
(body-carried wait, the pump inside the sequencer — there is no
wait_flow and no explicit pump call). One staging difference,
forced by the production design and stated plainly: the pump
runs inside the submission that lands X, so "land then retract
before the pump" (probe S3b) is staged as a land and a retract
inside ONE commit batch — the blind interval the findings
record as a residual. The semantics asserted are the probe's:
state-based, not edge-based.
"""
import pytest

from jacquard import (Sequencer, envelope_hash, fold,
                      install_lifecycles, make_envelope)
from jacquard.state import Refusal  # noqa: F401  (re-exported guard)


# ---------------------------------------------------------- fixtures

def landed_guard(unit, name):
    """A (map -> bool) word: true iff the committed unit exists
    and its "status" is "landed". Presence is tested with
    keys+contains before any getf, as in the probe."""
    body = [
        "drop",
        {"lit": unit}, "dup", "keys", "swap", "contains",
        {"if": [{"lit": unit}, "get",
                {"lit": "status"}, "getf",
                {"lit": "landed"}, "eq"],
         "else": [{"lit": False}]},
    ]
    examples = [
        {"args": [{"proposal_id": "example-landed"}],
         "state": {"units": {unit: {"status": "landed"}}},
         "expect": [True]},
        {"args": [{"proposal_id": "example-missing"}],
         "state": {"units": {}},
         "expect": [False]},
        {"args": [{"proposal_id": "example-retracted"}],
         "state": {"units": {unit: {"status": "retracted"}}},
         "expect": [False]},
    ]
    return {"name": name,
            "signature": {"ins": ["map"], "outs": ["bool"]},
            "body": body, "examples": examples}


DIV_GUARD = {
    "name": "cfg-is-three",
    "signature": {"ins": ["map"], "outs": ["bool"]},
    "body": ["drop", {"lit": "cfg/x"}, "get",
             {"lit": 10}, "swap", "div", {"lit": 3}, "eq"],
    "examples": [
        {"args": [{"proposal_id": "e1"}],
         "state": {"units": {"cfg/x": 3}}, "expect": [True]},
        {"args": [{"proposal_id": "e2"}],
         "state": {"units": {"cfg/x": 2}}, "expect": [False]}],
}


def kernel(guards=("x-landed",)):
    seq = Sequencer()
    verdicts = install_lifecycles(seq)
    assert all(v["status"] == "accepted" for v in verdicts.values())
    defs = {"x-landed": landed_guard("artifact/x", "x-landed"),
            "y-landed": landed_guard("artifact/y", "y-landed"),
            "w1-done": landed_guard("job/w1", "w1-done"),
            "cfg-is-three": DIV_GUARD}
    for name in guards:
        verdict = seq.submit(make_envelope(
            "operator", "definition", defs[name], [], "def-" + name))
        assert verdict["status"] == "accepted", verdict
        assert verdict["computed_effects"] == []
    return seq


def waiter_env(guard="x-landed", deadline=None, producer="agent-a",
               unit="job/w1", value=None, idem="w1-1", extra=None,
               declared=("write",)):
    body = {"requests": [{"verb": "write",
                          "args": [unit, {"job": "w1"}
                                   if value is None else value]}],
            "wait": {"guard": guard, "deadline_seq": deadline}}
    if extra:
        body["requests"] += extra["requests"]
        declared = extra["declared"]
    return make_envelope(producer, "proposal", body,
                         list(declared), idem)


def land(seq, unit="artifact/x", value=None, idem="land-1",
         producer="operator"):
    if value is None:
        value = {"status": "landed"}
    return seq.submit(make_envelope(
        producer, "proposal",
        {"requests": [{"verb": "write", "args": [unit, value]}]},
        ["write"], idem))


def far_deadline(seq):
    return len(seq.log.entries) + 1000


def executions_for(seq, proposal_id):
    return [e for e in seq.log.entries
            if e["kind"] == "execution"
            and e["body"].get("proposal_id") == proposal_id]


def decisions_for(seq, proposal_id):
    return [e for e in seq.log.entries
            if e["kind"] == "decision"
            and e["body"].get("proposal_id") == proposal_id]


# ---------------------------------------------------------- S1

def test_s1_x_lands_releases_waiter():
    seq = kernel()
    env = waiter_env(deadline=far_deadline(seq))
    pid = envelope_hash(env)
    verdict = seq.submit(env)
    assert verdict["status"] == "decided"
    assert verdict["outcome"] == "queue"
    assert verdict["reasons"] == ["waiting:x-landed"]
    queued = seq.state.decision_queue[pid]
    assert queued["wait"] == {"guard": "x-landed",
                              "deadline_seq": env["body"]["wait"]
                              ["deadline_seq"]}
    # Waiters are not approval items.
    assert "approval:" + pid not in seq.state.machine_instances
    assert seq.machine_instance_state(pid) == "tentative"
    assert executions_for(seq, pid) == []

    landing = land(seq)
    assert landing["outcome"] == "allow"
    # The pump ran inside the landing submission.
    executions = executions_for(seq, pid)
    assert len(executions) == 1
    assert executions[0]["body"]["applied"] == [
        {"verb": "write", "args": ["job/w1", {"job": "w1"}]}]
    assert seq.state.units["job/w1"] == {"job": "w1"}
    assert seq.state.decision_queue == {}
    release = [d for d in decisions_for(seq, pid)
               if d["body"].get("releases") == pid]
    assert len(release) == 1
    assert release[0]["body"]["reasons"] == ["wait-satisfied:x-landed"]
    assert seq.machine_instance_state(pid) == "closed"


# ---------------------------------------------------------- S2

def test_s2_x_never_lands_expires_by_deadline():
    seq = kernel()
    env = waiter_env(deadline=len(seq.log.entries) + 12)
    pid = envelope_hash(env)
    assert seq.submit(env)["outcome"] == "queue"
    assert pid in seq.state.decision_queue
    for i in range(30):
        if pid not in seq.state.decision_queue:
            break
        seq.checkpoint("unrelated-%d" % i)
    assert pid not in seq.state.decision_queue
    assert executions_for(seq, pid) == []
    assert "job/w1" not in seq.state.units
    expired = [d for d in decisions_for(seq, pid)
               if d["body"]["outcome"] == "expired"]
    assert len(expired) == 1
    assert expired[0]["body"]["reasons"] == ["wait-expired:x-landed"]
    assert expired[0]["body"]["expires"] == pid
    assert seq.machine_instance_state(pid) == "refused"


# ---------------------------------------------------------- S3a/S3b

def test_s3a_x_lands_twice_releases_exactly_once():
    seq = kernel()
    env = waiter_env(deadline=far_deadline(seq))
    pid = envelope_hash(env)
    seq.submit(env)
    land(seq, idem="land-1")
    assert len(executions_for(seq, pid)) == 1
    land(seq, value={"status": "landed", "note": "second"},
         idem="land-2")
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.decision_queue == {}


def test_s3b_land_and_retract_in_one_batch_does_not_start():
    seq = kernel()
    env = waiter_env(deadline=far_deadline(seq))
    pid = envelope_hash(env)
    seq.submit(env)
    # One proposal, two writes to the same unit: the committed
    # state the pump reads is "retracted" — the landing inside
    # the batch is never observed as landed.
    batch = seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [
            {"verb": "write",
             "args": ["artifact/x", {"status": "landed"}]},
            {"verb": "write",
             "args": ["artifact/x", {"status": "retracted"}]}]},
        ["write"], "land-retract-1"))
    assert batch["outcome"] == "allow"
    assert seq.state.units["artifact/x"] == {"status": "retracted"}
    assert executions_for(seq, pid) == []
    assert pid in seq.state.decision_queue
    # A later re-landing starts it.
    land(seq, idem="land-3")
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == {"job": "w1"}


# ---------------------------------------------------------- S4

def test_s4_two_waiters_release_in_queue_order():
    seq = kernel()
    deadline = far_deadline(seq)
    env_a = waiter_env(unit="job/w1", value={"job": "w1"},
                       idem="w-a", deadline=deadline)
    env_b = waiter_env(producer="agent-b", unit="job/w2",
                       value={"job": "w2"}, idem="w-b",
                       deadline=deadline)
    pid_a, pid_b = envelope_hash(env_a), envelope_hash(env_b)
    seq.submit(env_a)
    seq.submit(env_b)
    assert list(seq.state.decision_queue) == [pid_a, pid_b]
    land(seq)
    assert len(executions_for(seq, pid_a)) == 1
    assert len(executions_for(seq, pid_b)) == 1
    seqs = [executions_for(seq, pid_a)[0]["seq"],
            executions_for(seq, pid_b)[0]["seq"]]
    assert seqs == sorted(seqs)  # A executed before B
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- S5

def test_s5_guard_already_true_takes_normal_path():
    seq = kernel()
    land(seq)
    env = waiter_env(deadline=far_deadline(seq))
    pid = envelope_hash(env)
    verdict = seq.submit(env)
    assert verdict["outcome"] == "allow"
    assert verdict["reasons"] == ["wait-satisfied:x-landed"]
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == {"job": "w1"}
    assert seq.state.decision_queue == {}
    queued = [d for d in decisions_for(seq, pid)
              if d["body"]["outcome"] == "queued"]
    assert queued == []


# ---------------------------------------------------------- S7/S8

def test_s7_audit_chain_from_the_log():
    seq = kernel()
    env = waiter_env(deadline=far_deadline(seq))
    pid = envelope_hash(env)
    seq.submit(env)
    landing = land(seq)
    queued = [d for d in decisions_for(seq, pid)
              if d["body"]["outcome"] == "queued"]
    assert len(queued) == 1
    assert queued[0]["body"]["wait"]["guard"] == "x-landed"
    assert queued[0]["body"]["reasons"] == ["waiting:x-landed"]
    landing_exec = executions_for(seq, landing["proposal_id"])
    releases = [d for d in decisions_for(seq, pid)
                if d["body"].get("releases") == pid]
    assert len(releases) == 1
    assert landing_exec[0]["seq"] < releases[0]["seq"]
    assert queued[0]["seq"] < releases[0]["seq"]
    assert releases[0]["seq"] < executions_for(seq, pid)[0]["seq"]


def test_s8_mid_wait_refold_keeps_the_wait_spec():
    seq = kernel()
    wait = {"guard": "x-landed", "deadline_seq": far_deadline(seq)}
    env = waiter_env(deadline=wait["deadline_seq"])
    pid = envelope_hash(env)
    seq.submit(env)
    assert pid in seq.state.decision_queue  # still waiting
    folded = fold(seq.log.entries)
    assert folded.state_hash() == seq.state.state_hash()
    assert folded.decision_queue[pid]["wait"] == wait


# ---------------------------------------------------------- composition

def test_wait_composition_with_protected_effect():
    seq = kernel()
    extra = {"requests": [{"verb": "notify",
                           "args": ["ops", "w1 started"]}],
             "declared": ("write", "notify")}
    env = waiter_env(deadline=far_deadline(seq), extra=extra)
    pid = envelope_hash(env)
    assert seq.submit(env)["outcome"] == "queue"
    assert "approval:" + pid not in seq.state.machine_instances
    land(seq)
    # The fired guard re-decided through policy: notify is
    # protected, so the item is now an ORDINARY approval queue
    # entry — the wait is spent, an approval instance exists,
    # and nothing has executed.
    assert pid in seq.state.decision_queue
    queued = seq.state.decision_queue[pid]
    assert "wait" not in queued
    assert "approval:" + pid in seq.state.machine_instances
    assert executions_for(seq, pid) == []
    fired = [d for d in decisions_for(seq, pid)
             if d["body"]["outcome"] == "queued"][-1]
    assert "wait-satisfied:x-landed" in fired["body"]["reasons"]
    # The operator release executes it, as for any queued item.
    result = seq.release_queued(pid, "operator")
    assert result["outcome"] == "allow"
    assert len(executions_for(seq, pid)) == 1
    assert seq.state.units["job/w1"] == {"job": "w1"}


def test_wait_cascade_completes_in_one_submission():
    seq = kernel(guards=("x-landed", "w1-done"))
    deadline = far_deadline(seq)
    env_b = waiter_env(guard="w1-done", producer="agent-b",
                       unit="job/w2", value={"job": "w2"},
                       idem="w-b", deadline=deadline)
    env_a = waiter_env(unit="job/w1", value={"status": "landed"},
                       idem="w-a", deadline=deadline)
    pid_a, pid_b = envelope_hash(env_a), envelope_hash(env_b)
    seq.submit(env_b)   # B queued first, on a condition A creates
    seq.submit(env_a)
    land(seq)           # one submission completes both
    assert len(executions_for(seq, pid_a)) == 1
    assert len(executions_for(seq, pid_b)) == 1
    assert seq.state.units["job/w2"] == {"job": "w2"}
    assert seq.state.decision_queue == {}


# ---------------------------------------------------------- ordering

def test_guard_true_beats_deadline_at_the_same_pump():
    seq = kernel()
    env = waiter_env(deadline=len(seq.log.entries) + 8)
    pid = envelope_hash(env)
    deadline = env["body"]["wait"]["deadline_seq"]
    seq.submit(env)
    # Walk the log up to exactly the deadline with unrelated
    # entries; the guard is still false and nothing expires
    # (expiry is strictly past the deadline).
    i = 0
    while len(seq.log.entries) < deadline:
        seq.checkpoint("pad-%d" % i)
        i += 1
    assert pid in seq.state.decision_queue
    # The landing submission both passes the deadline and makes
    # the guard true: the waiter is released, not expired.
    land(seq)
    assert len(executions_for(seq, pid)) == 1
    assert [d for d in decisions_for(seq, pid)
            if d["body"]["outcome"] == "expired"] == []


# ---------------------------------------------------------- guard validation

def _submit_expect_refusal(seq, env, name):
    before = len(seq.log.entries)
    verdict = seq.submit(env)
    assert verdict["status"] == "REFUSED", verdict
    assert verdict["refusal"] == name, verdict
    assert len(seq.log.entries) == before  # nothing appended


def test_unknown_guard_refused_log_unchanged():
    seq = kernel()
    env = waiter_env(guard="no-such-word", deadline=far_deadline(seq))
    _submit_expect_refusal(seq, env, "SPEC")


def test_impure_guard_refused_log_unchanged():
    seq = kernel()
    impure = {"name": "impure-guard",
              "signature": {"ins": ["map"], "outs": ["bool"]},
              "body": ["dispatch", {"lit": True}],
              "examples": [{"args": [{"job": "x"}], "expect": [True],
                            "requests": ["dispatch"]}]}
    verdict = seq.submit(make_envelope(
        "operator", "definition", impure, [], "def-impure"))
    assert verdict["computed_effects"] == ["dispatch"]
    env = waiter_env(guard="impure-guard", deadline=far_deadline(seq))
    _submit_expect_refusal(seq, env, "SPEC")


def test_wrong_signature_guard_refused_log_unchanged():
    seq = kernel()
    double = {"name": "double",
              "signature": {"ins": ["int"], "outs": ["int"]},
              "body": ["dup", "add"],
              "examples": [{"args": [2], "expect": [4]}]}
    verdict = seq.submit(make_envelope(
        "operator", "definition", double, [], "def-double"))
    assert verdict["status"] == "accepted"
    env = waiter_env(guard="double", deadline=far_deadline(seq))
    _submit_expect_refusal(seq, env, "FIELD")


@pytest.mark.parametrize("wait", [
    "x-landed",                                   # not a dict
    {"guard": "x-landed"},                        # no deadline
    {"deadline_seq": 10},                         # no guard
    {"guard": 7, "deadline_seq": 10},             # guard not str
    {"guard": "x-landed", "deadline_seq": True},  # bool deadline
    {"guard": "x-landed", "deadline_seq": "10"},  # str deadline
])
def test_malformed_wait_refused_log_unchanged(wait):
    seq = kernel()
    env = make_envelope(
        "agent-a", "proposal",
        {"requests": [{"verb": "write",
                       "args": ["job/w1", {"job": "w1"}]}],
         "wait": wait},
        ["write"], "w-bad")
    _submit_expect_refusal(seq, env, "FIELD")


def test_submission_time_guard_refusal_is_a_submission_refusal():
    seq = kernel(guards=("cfg-is-three",))
    land(seq, unit="cfg/x", value=0, idem="cfg-0")
    env = waiter_env(guard="cfg-is-three", deadline=far_deadline(seq))
    _submit_expect_refusal(seq, env, "FIELD")  # 10 / 0 refuses


# ---------------------------------------------------------- refusing guards

def test_pump_time_guard_refusal_is_recorded_not_fatal():
    seq = kernel(guards=("cfg-is-three",))
    land(seq, unit="cfg/x", value=2, idem="cfg-2")  # 10/2=5 != 3
    env = waiter_env(guard="cfg-is-three",
                     deadline=len(seq.log.entries) + 40)
    pid = envelope_hash(env)
    assert seq.submit(env)["outcome"] == "queue"

    # cfg/x := 0 makes the guard raise at re-evaluation. The
    # unrelated submission succeeds; the refusal is recorded on
    # the waiter's queue entry; the waiter stays queued.
    verdict = land(seq, unit="cfg/x", value=0, idem="cfg-0")
    assert verdict["outcome"] == "allow"
    assert pid in seq.state.decision_queue
    assert executions_for(seq, pid) == []
    records = [d for d in decisions_for(seq, pid)
               if d["body"]["reasons"] ==
               ["wait-guard-refused:FIELD"]]
    assert len(records) == 1
    assert records[0]["body"]["wait"]["guard"] == "cfg-is-three"
    assert records[0]["body"]["wait_refusal_at"] == \
        records[0]["seq"]

    # cfg/x := 5 makes the guard false again (10/5=2 != 3); the
    # deadline then expires the waiter with the wait reason.
    land(seq, unit="cfg/x", value=5, idem="cfg-5")
    for i in range(60):
        if pid not in seq.state.decision_queue:
            break
        seq.checkpoint("drain-%d" % i)
    assert pid not in seq.state.decision_queue
    expired = [d for d in decisions_for(seq, pid)
               if d["body"]["outcome"] == "expired"]
    assert len(expired) == 1
    assert expired[0]["body"]["reasons"] == \
        ["wait-expired:cfg-is-three"]
    assert executions_for(seq, pid) == []


# ---------------------------------------------------------- reason parameter

def test_reason_parameter_defaults_and_override():
    seq = kernel(guards=())
    def queued_notify(idem):
        verdict = seq.submit(make_envelope(
            "alice", "proposal",
            {"requests": [{"verb": "notify", "args": ["ops", "hi"]}]},
            ["notify"], idem))
        assert verdict["outcome"] == "queue"
        return verdict["proposal_id"]

    pid = queued_notify("n-1")
    seq.release_queued(pid, "operator")
    release = decisions_for(seq, pid)[-1]
    assert release["body"]["reasons"] == ["released-by-operator"]

    pid = queued_notify("n-2")
    seq.release_queued(pid, "operator", reason="because:batch-7")
    assert decisions_for(seq, pid)[-1]["body"]["reasons"] == \
        ["because:batch-7"]

    pid = queued_notify("n-3")
    seq.reject_queued(pid, "operator", reason="preempted-by:W")
    assert decisions_for(seq, pid)[-1]["body"]["reasons"] == \
        ["preempted-by:W"]

    pid = queued_notify("n-4")
    seq.expire_queued(pid, "operator")
    assert decisions_for(seq, pid)[-1]["body"]["reasons"] == \
        ["expired-in-queue"]
