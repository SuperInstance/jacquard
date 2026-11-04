"""The MCode adapter (Phase 14, slice 39): adapters/mcode_hook.py
driven as a process-shaped unit -- events in on stdin, verdict
JSON out -- against a real kernel log in a temp dir.

Covered: the captured real-host fixture fast-paths (MCode
0.6.13 payloads, tests/data/mcode/); a write queues with the
proposal id + binding hash in the deny reason and is never
duplicated; an operator release authorises exactly one retry
(consumption is a log entry); a rejection is terminal for the
identical action; unmapped host tools pass silently; a
released shell action's PostToolUse outcome is reported
against its action machine; a corrupt log fails closed; the
latency sidecar records every invocation; camelCase event
spellings are accepted alongside MCode's native snake_case.
"""
import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402
from jacquard.coding_agent import consumptions  # noqa: E402

_HOOK_PATH = os.path.join(os.path.dirname(__file__), "..",
                          "adapters", "mcode_hook.py")
_spec = importlib.util.spec_from_file_location("mcode_hook",
                                               _HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

DATA = os.path.join(os.path.dirname(__file__), "data", "mcode")


def fixture(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def run_hook(event, log_path, monkeypatch):
    """Invoke the hook's main() the way the host does."""
    monkeypatch.setenv("JACQUARD_LOG", str(log_path))
    monkeypatch.setattr(sys, "stdin",
                        io.StringIO(json.dumps(event)))
    out = io.StringIO()
    with redirect_stdout(out):
        rc = hook.main()
    assert rc == 0
    text = out.getvalue().strip()
    return json.loads(text) if text else None


def write_event(content="print(1)", path="/tmp/x.py"):
    return {"hook_event_name": "PreToolUse", "tool_name": "write",
            "tool_input": {"path": path, "content": content},
            "cwd": "/tmp"}


def verdict_of(event, log_path, monkeypatch):
    result = run_hook(event, log_path, monkeypatch)
    assert result is not None
    return result["hookSpecificOutput"]


def kernel(log_path):
    return Sequencer(Log(str(log_path)))


def sidecar(log_path):
    path = str(log_path) + ".latency.jsonl"
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path)]


def test_captured_fixture_read_fast_paths(tmp_path, monkeypatch):
    event = fixture("pretooluse-read.json")
    log_path = tmp_path / "kernel.jsonl"
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "allow"
    seq = kernel(log_path)
    decisions = [e for e in seq.log.entries
                 if e["kind"] == "decision"]
    assert decisions and decisions[-1]["body"]["outcome"] == "allow"
    lines = sidecar(log_path)
    assert lines and lines[-1]["verdict"] == "allow"
    assert lines[-1]["tool"] == "read"


def test_captured_fixture_write_queues(tmp_path, monkeypatch):
    event = fixture("pretooluse-write.json")
    log_path = tmp_path / "kernel.jsonl"
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED" in out["permissionDecisionReason"]
    assert len(kernel(log_path).state.decision_queue) == 1


def test_captured_fixture_bash_queues(tmp_path, monkeypatch):
    event = fixture("pretooluse-bash.json")
    log_path = tmp_path / "kernel.jsonl"
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED" in out["permissionDecisionReason"]
    assert len(kernel(log_path).state.decision_queue) == 1


def test_write_queues_once_with_binding_hash(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    out = verdict_of(write_event(), log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    assert "QUEUED" in reason
    seq = kernel(log_path)
    assert len(seq.state.decision_queue) == 1
    pid = next(iter(seq.state.decision_queue))
    assert pid in reason
    assert hook.binding_hash(seq, pid) in reason
    # The identical call again: same item, no duplicate.
    out2 = verdict_of(write_event(), log_path, monkeypatch)
    assert out2["permissionDecision"] == "deny"
    assert pid in out2["permissionDecisionReason"]
    assert len(kernel(log_path).state.decision_queue) == 1


def test_release_authorises_exactly_one_retry(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    verdict_of(write_event(), log_path, monkeypatch)
    seq = kernel(log_path)
    pid = next(iter(seq.state.decision_queue))
    seq.release_queued(pid, "operator")
    out = verdict_of(write_event(), log_path, monkeypatch)
    assert out["permissionDecision"] == "allow"
    assert consumptions(kernel(log_path), pid) == 1
    # One-shot: the next identical call queues as a NEW item.
    out2 = verdict_of(write_event(), log_path, monkeypatch)
    assert out2["permissionDecision"] == "deny"
    seq2 = kernel(log_path)
    assert len(seq2.state.decision_queue) == 1
    assert next(iter(seq2.state.decision_queue)) != pid


def test_rejection_is_terminal_for_the_identical_action(
        tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    verdict_of(write_event(), log_path, monkeypatch)
    seq = kernel(log_path)
    pid = next(iter(seq.state.decision_queue))
    seq.reject_queued(pid, "operator")
    out = verdict_of(write_event(), log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    assert "already denied" in out["permissionDecisionReason"]
    assert kernel(log_path).state.decision_queue == {}


def test_changed_action_is_a_new_proposal(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    verdict_of(write_event(), log_path, monkeypatch)
    seq = kernel(log_path)
    seq.reject_queued(next(iter(seq.state.decision_queue)),
                      "operator")
    out = verdict_of(write_event(content="print(2)"), log_path,
                     monkeypatch)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED" in out["permissionDecisionReason"]
    assert len(kernel(log_path).state.decision_queue) == 1


def test_unmapped_tool_passes_silently(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    event = {"hook_event_name": "PreToolUse", "tool_name": "task",
             "tool_input": {"prompt": "do something"}, "cwd": "/tmp"}
    assert run_hook(event, log_path, monkeypatch) is None
    lines = sidecar(log_path)
    assert lines and lines[-1]["outcome"] == "pass"
    assert not os.path.exists(log_path)  # kernel never touched


def test_shell_outcome_reported_after_execution(tmp_path,
                                                monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    event = {"hook_event_name": "PreToolUse", "tool_name": "bash",
             "tool_input": {"command": "echo hi"}, "cwd": "/tmp"}
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    seq = kernel(log_path)
    pid = next(iter(seq.state.decision_queue))
    seq.release_queued(pid, "operator")
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "allow"
    machine = kernel(log_path).state.machine_instances[
        "%s/action-0" % pid]
    assert machine["state"] == "dispatched"
    post = dict(event, hook_event_name="PostToolUse",
                tool_response={"content": [{"type": "text",
                                             "text": "hi"}]})
    assert run_hook(post, log_path, monkeypatch) is None
    machine = kernel(log_path).state.machine_instances[
        "%s/action-0" % pid]
    assert machine["state"] == "confirmed"


def test_corrupt_log_fails_closed(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    log_path.write_bytes(b"this is not a log\n")
    out = verdict_of(write_event(), log_path, monkeypatch)
    assert out["permissionDecision"] == "deny"
    assert "adapter error" in out["permissionDecisionReason"]


def test_camel_case_event_spelling_accepted(tmp_path, monkeypatch):
    log_path = tmp_path / "kernel.jsonl"
    event = {"hookEventName": "PreToolUse", "toolName": "read",
             "toolInput": {"path": "/tmp/x.py"}, "cwd": "/tmp"}
    out = verdict_of(event, log_path, monkeypatch)
    assert out["permissionDecision"] == "allow"
