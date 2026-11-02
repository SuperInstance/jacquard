"""Behaviour specs for the seven lifecycle machines, and for the
kernel paths that run through them (proposal, action, approval,
producer standing). A behaviour spec drives an event sequence and
asserts the resulting state plus the transitions the log shows.
"""
from jacquard import Sequencer, install_lifecycles, make_envelope


def kernel():
    seq = Sequencer()
    verdicts = install_lifecycles(seq)
    assert all(v["status"] == "accepted" for v in verdicts.values())
    return seq


def drive(seq, machine, instance, events):
    seq.create_machine_instance(machine, instance)
    results = [seq.step_machine(instance, event) for event in events]
    return results


# --------------------------------------------- behaviour specs

def test_proposal_machine_happy_path():
    seq = kernel()
    results = drive(seq, "proposal", "p-x",
                    ["submit", "decide", "commit", "close"])
    assert [r["to"] for r in results] == ["validated", "decided",
                                          "committed", "closed"]
    assert seq.machine_instance_state("p-x") == "closed"


def test_proposal_machine_queue_path():
    seq = kernel()
    drive(seq, "proposal", "p-y", ["submit", "hold", "decide",
                                   "commit", "close"])
    assert seq.machine_instance_state("p-y") == "closed"


def test_action_machine_failure_path():
    seq = kernel()
    drive(seq, "action", "a-1", ["approve", "dispatch", "fail",
                                 "compensate"])
    assert seq.machine_instance_state("a-1") == "compensated"


def test_standing_rule_machine_full_lifecycle():
    seq = kernel()
    drive(seq, "standing-rule", "rule-1",
          ["evaluate", "deploy", "promote", "activate", "regress",
           "resubmit", "promote", "activate", "revoke"])
    assert seq.machine_instance_state("rule-1") == "revoked"


def test_producer_standing_machine_cycles():
    seq = kernel()
    drive(seq, "producer-standing", "producer:bob",
          ["degrade", "limit", "suspend", "reinstate", "resume"])
    assert seq.machine_instance_state("producer:bob") == "normal"


def test_commit_batch_machine():
    seq = kernel()
    drive(seq, "commit-batch", "batch-1", ["seal", "fold"])
    assert seq.machine_instance_state("batch-1") == "folded"
    drive(seq, "commit-batch", "batch-2", ["abort"])
    assert seq.machine_instance_state("batch-2") == "aborted"


def test_approval_machine_paths():
    seq = kernel()
    drive(seq, "approval", "ap-1", ["present", "approve"])
    assert seq.machine_instance_state("ap-1") == "approved"
    drive(seq, "approval", "ap-2", ["expire"])
    assert seq.machine_instance_state("ap-2") == "expired"


def test_worker_machine_paths():
    seq = kernel()
    drive(seq, "worker", "w-1", ["start", "fail", "start", "degrade",
                                 "recover", "stop"])
    assert seq.machine_instance_state("w-1") == "stopped"


# --------------------------------------- kernel paths via machines

def transitions_for(seq, instance):
    return [(e["body"]["event"], e["body"]["from"], e["body"]["to"],
             e["body"]["outcome"])
            for e in seq.log.entries
            if e["kind"] == "transition"
            and e["body"]["instance"] == instance]


def test_allowed_proposal_runs_through_its_machine():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "write", "args": ["answer", 42]}]},
        ["write"], "lp-1"))
    pid = verdict["proposal_id"]
    assert verdict["outcome"] == "allow"
    assert seq.machine_instance_state(pid) == "closed"
    path = [(frm, to) for (_e, frm, to, _o) in transitions_for(seq, pid)
            if _o == "taken"]
    assert path == [("received", "validated"), ("validated", "decided"),
                    ("decided", "committed"), ("committed", "closed")]


def test_queued_then_released_proposal_runs_through_machines():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "hi"]}]},
        ["notify"], "lp-2"))
    pid = verdict["proposal_id"]
    assert verdict["outcome"] == "queue"
    assert seq.machine_instance_state(pid) == "tentative"
    assert seq.machine_instance_state("approval:" + pid) == "pending"
    seq.release_queued(pid, "operator")
    assert seq.machine_instance_state(pid) == "closed"
    assert seq.machine_instance_state("approval:" + pid) == "approved"
    events = [e for (e, _f, _t, _o) in transitions_for(seq, "approval:" + pid)]
    assert events == ["@create", "present", "approve"]


def test_rejected_proposal_closes_both_machines():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "send", "args": ["x", 1]}]},
        ["send"], "lp-3"))
    pid = verdict["proposal_id"]
    seq.reject_queued(pid, "operator")
    assert seq.machine_instance_state(pid) == "refused"
    assert seq.machine_instance_state("approval:" + pid) == "denied"
    assert pid not in seq.state.decision_queue


def test_expired_proposal_closes_both_machines():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "send", "args": ["x", 1]}]},
        ["send"], "lp-4"))
    pid = verdict["proposal_id"]
    seq.expire_queued(pid, "operator")
    assert seq.machine_instance_state(pid) == "refused"
    assert seq.machine_instance_state("approval:" + pid) == "expired"


def test_dispatch_creates_action_instance_and_reports_outcomes():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "dispatch", "args": [{"job": "j-1"}]}]},
        ["dispatch"], "lp-5"))
    action_id = verdict["proposal_id"] + "/action-0"
    assert seq.machine_instance_state(action_id) == "dispatched"
    seq.report_action(action_id, "fail")
    assert seq.machine_instance_state(action_id) == "failed"
    seq.report_action(action_id, "compensate")
    assert seq.machine_instance_state(action_id) == "compensated"


def test_underdeclared_proposal_is_refused_in_its_machine():
    seq = kernel()
    verdict = seq.submit(make_envelope(
        "mallory", "proposal",
        {"requests": [{"verb": "write", "args": ["vault", "open"]},
                      {"verb": "send", "args": ["loot", 1]}]},
        ["write"], "lp-6"))
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"
    assert seq.machine_instance_state(verdict["proposal_id"]) == "refused"


def test_standing_transitions_reach_the_policy_gate():
    seq = kernel()
    seq.transition_standing("carol", "suspend")
    assert seq.standing["carol"] == {"status": "suspended"}
    verdict = seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "write", "args": ["a", 1]}]},
        ["write"], "lp-7"))
    assert verdict["outcome"] == "deny"
    seq.transition_standing("carol", "reinstate")
    seq.transition_standing("carol", "resume")
    assert seq.standing["carol"] == {"status": "normal"}
    verdict = seq.submit(make_envelope(
        "carol", "proposal",
        {"requests": [{"verb": "write", "args": ["a", 1]}]},
        ["write"], "lp-8"))
    assert verdict["outcome"] == "allow"


def test_bare_kernel_without_lifecycles_is_unchanged():
    seq = Sequencer()
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "write", "args": ["answer", 42]}]},
        ["write"], "lp-9"))
    assert verdict["outcome"] == "allow"
    assert seq.state.machine_instances == {}
