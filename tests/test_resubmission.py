"""Resubmission semantics (SPEC 3.1, spec 0.7).

Phase 13's `jq submit` build found the kernel's verdict cache
was per-process: a fresh-process resubmission of an identical
envelope was re-decided -- an allowed duplicate silently
re-executed, a queued duplicate appended a second decision
and crashed on machine-instance creation, a refused duplicate
appended a second refusal. Spec 0.7 settles the contract:
once a submission is recorded in the log, resubmission
returns the recorded verdict, marked "duplicate": true, and
never re-decides, never re-executes, never appends. The
check is against the log, so every test here resubmits
through a FRESH Sequencer built over the same entries --
the cross-process shape the shipped adapters actually have
(a fresh process per ZCode hook call).
"""
import copy

from jacquard import LIFECYCLES, Log, Sequencer, make_envelope, records
from jacquard.coding_agent import install_coding_agent, submit_tool_action


def fresh(seq):
    """A new sequencer over the same entries -- a new process."""
    log = Log()
    log.entries = copy.deepcopy(seq.log.entries)
    return Sequencer(log)


def proposal(producer, body, declared, idem):
    return make_envelope(producer, "proposal", body, declared, idem)


def submission_decisions(seq, pid):
    return [e for e in seq.log.entries
            if e["kind"] == "decision"
            and e["body"].get("proposal_id") == pid
            and not any(k in e["body"]
                        for k in ("releases", "rejects", "expires"))]


def executions(seq, pid):
    return [e for e in seq.log.entries
            if e["kind"] == "execution"
            and e["body"].get("proposal_id") == pid]


WRITE = {"requests": [{"verb": "write", "args": ["u", 1]}]}
SEND = {"requests": [{"verb": "send", "args": ["ops", "hello"]}]}


def test_duplicate_allowed_never_reexecutes():
    seq = Sequencer()
    env = proposal("agent-a", WRITE, ["write"], "a1")
    first = seq.submit(env)
    assert first["outcome"] == "allow"
    assert len(executions(seq, first["proposal_id"])) == 1
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    seq2 = fresh(seq)
    assert len(seq2.log.entries) == count
    assert len(executions(seq2, first["proposal_id"])) == 1
    assert len(submission_decisions(seq2, first["proposal_id"])) == 1


def test_duplicate_queued_never_requeues_or_crashes():
    # With the lifecycle machines installed this is the shape
    # that crashed in 0.6 (second approval-instance creation).
    from jacquard import install_lifecycles
    seq = Sequencer()
    install_lifecycles(seq)
    env = proposal("agent-a", SEND, ["send"], "q1")
    first = seq.submit(env)
    assert first["outcome"] == "queue"
    pid = first["proposal_id"]
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    seq2 = fresh(seq)
    assert len(seq2.log.entries) == count
    assert list(seq2.state.decision_queue) == [pid]
    assert len(submission_decisions(seq2, pid)) == 1
    # The queued item is still decidable, exactly once.
    released = seq2.release_queued(pid, "operator")
    assert released["outcome"] == "allow"
    assert len(executions(seq2, pid)) == 1


def test_duplicate_denied_replays_deny():
    seq = Sequencer(standing={"bad": {"status": "suspended"}})
    env = proposal("bad", WRITE, ["write"], "d1")
    first = seq.submit(env)
    assert first["outcome"] == "deny"
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    assert len(fresh(seq).log.entries) == count


def test_duplicate_refused_records_one_fault():
    seq = Sequencer()
    env = proposal("agent-a",
                   {"requests": [{"verb": "dispatch",
                                  "args": [{"job": "x"}]}]},
                   ["reads"], "u1")
    first = seq.submit(env)
    assert first["status"] == "REFUSED"
    assert first["refusal"] == "UNDERDECLARED"
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    seq2 = fresh(seq)
    assert len(seq2.log.entries) == count
    view = records(seq2.log.entries)
    assert view["agent-a"]["work"]["faults"] == 1


def test_duplicate_across_checkpoint_boundary():
    seq = Sequencer()
    env = proposal("agent-a", WRITE, ["write"], "c1")
    first = seq.submit(env)
    seq.checkpoint("after-first")
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    assert len(fresh(seq).log.entries) == count


def test_duplicate_after_release_returns_submission_verdict():
    # SPEC 3.1: later operator decisions do not change the
    # recorded verdict. The item was released and executed;
    # a resubmission still hears "queue" (its submission
    # verdict), marked as a replay, and nothing re-executes.
    seq = Sequencer()
    env = proposal("agent-a", SEND, ["send"], "r1")
    first = seq.submit(env)
    pid = first["proposal_id"]
    seq2 = fresh(seq)
    seq2.release_queued(pid, "operator")
    assert len(executions(seq2, pid)) == 1
    count = len(seq2.log.entries)
    second = fresh(seq2).submit(env)
    assert second == dict(first, duplicate=True)
    assert second["outcome"] == "queue"
    seq3 = fresh(seq2)
    assert len(seq3.log.entries) == count
    assert len(executions(seq3, pid)) == 1


def test_duplicate_after_expire_returns_submission_verdict():
    # The shape the 0.6 jq verb crashed on (its outcome map
    # had no "expired"): the kernel answers it by contract.
    seq = Sequencer()
    env = proposal("agent-a", SEND, ["send"], "e1")
    first = seq.submit(env)
    pid = first["proposal_id"]
    seq2 = fresh(seq)
    seq2.expire_queued(pid, "operator")
    count = len(seq2.log.entries)
    second = fresh(seq2).submit(env)
    assert second == dict(first, duplicate=True)
    assert len(fresh(seq2).log.entries) == count


def test_duplicate_definition_replays_acceptance():
    seq = Sequencer()
    defn = {"name": "double",
            "signature": {"ins": ["int"], "outs": ["int"]},
            "body": ["dup", "add"],
            "examples": [{"args": [2], "expect": [4]}]}
    env = make_envelope("operator", "definition", defn, [], "def-1")
    first = seq.submit(env)
    assert first["status"] == "accepted"
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    assert len(fresh(seq).log.entries) == count


def test_duplicate_machine_replays_acceptance():
    seq = Sequencer()
    env = make_envelope("operator", "machine",
                        {"text": LIFECYCLES["commit-batch"]}, [], "m-1")
    first = seq.submit(env)
    assert first["status"] == "accepted"
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    assert len(fresh(seq).log.entries) == count


def test_define_check_refusal_is_recorded_and_replays():
    # A proposal whose embedded definition fails its check:
    # since 0.7 the refusal records one fault decision, so a
    # cross-process duplicate replays it and appends nothing.
    seq = Sequencer()
    bad = {"name": "broken",
           "signature": {"ins": [], "outs": []},
           "body": [], "examples": [{"args": [], "expect": [1]}]}
    env = proposal("agent-a",
                   {"requests": [{"verb": "write", "args": ["u", 1]},
                                 {"verb": "define", "args": [bad]}]},
                   ["write", "define"], "at-dup")
    first = seq.submit(env)
    assert first["status"] == "REFUSED"
    pid = first["proposal_id"]
    assert len(submission_decisions(seq, pid)) == 1
    count = len(seq.log.entries)
    second = fresh(seq).submit(env)
    assert second == dict(first, duplicate=True)
    seq2 = fresh(seq)
    assert len(seq2.log.entries) == count
    assert len(submission_decisions(seq2, pid)) == 1
    assert "u" not in seq2.state.units


def test_adapter_path_duplicate_delivery():
    # The ZCode hook shape: the same tool call delivered to
    # two fresh processes (two fresh sequencers over the same
    # log), submitted through the coding-agent profile with
    # the same idempotency id -- e.g. a retry after the first
    # response was lost. One proposal, one decision, and the
    # second delivery hears the recorded verdict.
    seq = Sequencer()
    install_coding_agent(seq)
    payload = {"unit": "agent-file:/tmp/x.py",
               "value": {"path": "/tmp/x.py", "content": "print(1)"}}
    first = submit_tool_action(seq, "zcode-agent", "agent-write",
                               payload, "hook-call-1")
    assert first["outcome"] == "queue"
    pid = first["proposal_id"]
    count = len(seq.log.entries)
    second = submit_tool_action(fresh(seq), "zcode-agent",
                                "agent-write", payload, "hook-call-1")
    assert second == dict(first, duplicate=True)
    seq2 = fresh(seq)
    assert len(seq2.log.entries) == count
    assert list(seq2.state.decision_queue) == [pid]
    assert len(submission_decisions(seq2, pid)) == 1


def test_in_process_duplicate_is_marked_too():
    seq = Sequencer()
    env = proposal("agent-a", WRITE, ["write"], "ip1")
    first = seq.submit(env)
    second = seq.submit(env)
    assert second == dict(first, duplicate=True)
    third = fresh(seq).submit(env)
    assert third == second
