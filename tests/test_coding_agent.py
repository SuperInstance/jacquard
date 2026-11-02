"""The coding-agent profile (Phase 5, slice 12): the four
tool-class words install against the profile checker with the
computed effects the profile table claims; the policy data
fast-paths reads and queues writes / shell / network actions;
an operator release is consumable exactly once.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402
from jacquard.coding_agent import (  # noqa: E402
    EXPECTED_EFFECTS, TOOL_CLASSES, binding_hash, consumptions,
    find_unconsumed_release, install_coding_agent, mark_consumed,
    prepare_requests, profile_installed, submit_tool_action)


def kernel(tmp_path):
    seq = Sequencer(Log(str(tmp_path / "kernel.jsonl")))
    install_coding_agent(seq)
    return seq


def test_profile_installs_and_effects_are_computed(tmp_path):
    seq = Sequencer(Log(str(tmp_path / "kernel.jsonl")))
    verdicts = install_coding_agent(seq)
    assert profile_installed(seq)
    for name, expected in EXPECTED_EFFECTS.items():
        assert verdicts["definitions"][name]["status"] == "accepted"
        assert verdicts["definitions"][name]["computed_effects"] == expected
        stored = seq.state.dictionary[name][-1]["definition"]
        assert stored["computed_effects"] == expected


def test_policy_is_data_with_a_row_per_class():
    for name in EXPECTED_EFFECTS:
        assert name in TOOL_CLASSES
        assert TOOL_CLASSES[name]["word"] == name
    assert TOOL_CLASSES["agent-read"]["gate"] == "allow"
    for name in ("agent-write", "agent-shell", "agent-network"):
        assert TOOL_CLASSES[name]["gate"] == "queue"


def test_read_fast_paths(tmp_path):
    seq = kernel(tmp_path)
    verdict = submit_tool_action(seq, "zcode-agent", "agent-read",
                                 {"path": "agent/note"}, "r1")
    assert verdict["outcome"] == "allow"
    assert seq.state.decision_queue == {}


def test_write_shell_and_network_queue(tmp_path):
    seq = kernel(tmp_path)
    write = submit_tool_action(
        seq, "zcode-agent", "agent-write",
        {"unit": "agent-file:/tmp/x.py",
         "value": {"path": "/tmp/x.py", "content": "print(1)"}}, "w1")
    assert write["outcome"] == "queue"
    assert write["reasons"] == ["protected-effect:notify"]
    shell = submit_tool_action(seq, "zcode-agent", "agent-shell",
                               {"cmd": ["echo", "hi"]}, "s1")
    assert shell["outcome"] == "queue"
    network = submit_tool_action(
        seq, "zcode-agent", "agent-network",
        {"channel": "https://example.com", "payload": {}}, "n1")
    assert network["outcome"] == "queue"
    assert network["reasons"] == ["protected-effect:send"]
    assert len(seq.state.decision_queue) == 3
    for pid in (write["proposal_id"], shell["proposal_id"],
                network["proposal_id"]):
        assert binding_hash(seq, pid)


def test_queued_requests_carry_the_real_effect_plus_the_gate(tmp_path):
    seq = kernel(tmp_path)
    requests = prepare_requests(
        seq, "zcode-agent", "agent-write",
        {"unit": "agent-file:/tmp/x.py",
         "value": {"path": "/tmp/x.py", "content": "print(1)"}})
    assert [r["verb"] for r in requests] == ["write", "notify"]
    assert requests[0]["args"][0] == "agent-file:/tmp/x.py"
    requests = prepare_requests(seq, "zcode-agent", "agent-shell",
                                {"cmd": ["echo", "hi"]})
    assert [r["verb"] for r in requests] == ["dispatch", "notify"]
    assert requests[0]["args"][0] == {"cmd": ["echo", "hi"]}


def test_release_is_consumed_exactly_once(tmp_path):
    seq = kernel(tmp_path)
    payload = {"unit": "agent-file:/tmp/x.py",
               "value": {"path": "/tmp/x.py", "content": "print(1)"}}
    verdict = submit_tool_action(seq, "zcode-agent", "agent-write",
                                 payload, "w1")
    pid = verdict["proposal_id"]
    requests = prepare_requests(seq, "zcode-agent", "agent-write", payload)
    assert find_unconsumed_release(seq, "zcode-agent", "agent-write",
                                   requests) is None
    seq.release_queued(pid, "operator")
    assert find_unconsumed_release(seq, "zcode-agent", "agent-write",
                                   requests) == pid
    mark_consumed(seq, pid, "zcode-agent")
    assert consumptions(seq, pid) == 1
    assert find_unconsumed_release(seq, "zcode-agent", "agent-write",
                                   requests) is None


def test_rejected_proposal_grants_no_release(tmp_path):
    seq = kernel(tmp_path)
    payload = {"unit": "agent-file:/tmp/x.py",
               "value": {"path": "/tmp/x.py", "content": "print(1)"}}
    verdict = submit_tool_action(seq, "zcode-agent", "agent-write",
                                 payload, "w1")
    seq.reject_queued(verdict["proposal_id"], "operator")
    requests = prepare_requests(seq, "zcode-agent", "agent-write", payload)
    assert find_unconsumed_release(seq, "zcode-agent", "agent-write",
                                   requests) is None
