"""The ZCode hook adapter (Phase 5, slice 12): verdict
translation over REAL captured ZCode hook payloads
(tests/data/zcode/, see its PROVENANCE.md), the
queue -> operator approval -> retry-consumes-approval flow,
the denied-stays-denied flow, fail-closed error paths, and
the latency sidecar shape.
"""
import importlib.util
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402
from jacquard.coding_agent import binding_hash  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
HOOK = os.path.join(ROOT, "adapters", "zcode_hook.py")
DATA = os.path.join(os.path.dirname(__file__), "data", "zcode")

_spec = importlib.util.spec_from_file_location("zcode_hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def fixture(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def run_hook(event, log_path, extra_env=None):
    env = dict(os.environ)
    env["JACQUARD_LOG"] = str(log_path)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, HOOK], input=json.dumps(event),
        capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]


# ---------------------------------------------------------- allow

def test_real_read_payload_fast_paths(tmp_path):
    log = tmp_path / "kernel.jsonl"
    out = run_hook(fixture("pretooluse-read.json"), log)
    assert out["permissionDecision"] == "allow"
    seq = Sequencer(Log(str(log)))
    assert seq.state.decision_queue == {}


def test_real_write_payload_queues_with_binding_in_reason(tmp_path):
    log = tmp_path / "kernel.jsonl"
    event = fixture("pretooluse-write.json")
    out = run_hook(event, log)
    assert out["permissionDecision"] == "deny"
    reason = out["permissionDecisionReason"]
    assert "QUEUED for operator decision" in reason
    seq = Sequencer(Log(str(log)))
    (pid,) = list(seq.state.decision_queue)
    assert pid in reason
    assert binding_hash(seq, pid) in reason


def test_real_bash_payload_queues(tmp_path):
    log = tmp_path / "kernel.jsonl"
    out = run_hook(fixture("pretooluse-bash.json"), log)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED for operator decision" in out["permissionDecisionReason"]


def test_queued_retry_reports_the_same_item(tmp_path):
    log = tmp_path / "kernel.jsonl"
    event = fixture("pretooluse-write.json")
    first = run_hook(event, log)
    second = run_hook(event, log)
    assert first["permissionDecisionReason"] == \
        second["permissionDecisionReason"]
    seq = Sequencer(Log(str(log)))
    assert len(seq.state.decision_queue) == 1


# ---------------------------------------------------------- approval

def test_approval_lets_one_retry_through_then_requeues(tmp_path):
    log = tmp_path / "kernel.jsonl"
    event = fixture("pretooluse-write.json")
    run_hook(event, log)
    seq = Sequencer(Log(str(log)))
    (pid,) = list(seq.state.decision_queue)
    seq.release_queued(pid, "operator")
    out = run_hook(event, log)
    assert out["permissionDecision"] == "allow"
    assert pid in out["permissionDecisionReason"]
    # The approval is spent: the next identical action queues anew.
    out = run_hook(event, log)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED for operator decision" in out["permissionDecisionReason"]


def test_operator_deny_is_terminal_for_the_exact_action(tmp_path):
    log = tmp_path / "kernel.jsonl"
    event = fixture("pretooluse-write.json")
    run_hook(event, log)
    seq = Sequencer(Log(str(log)))
    (pid,) = list(seq.state.decision_queue)
    seq.reject_queued(pid, "operator")
    out = run_hook(event, log)
    assert out["permissionDecision"] == "deny"
    assert "already denied" in out["permissionDecisionReason"]
    seq = Sequencer(Log(str(log)))
    assert seq.state.decision_queue == {}


def test_changed_action_is_a_new_proposal(tmp_path):
    log = tmp_path / "kernel.jsonl"
    event = fixture("pretooluse-write.json")
    run_hook(event, log)
    changed = json.loads(json.dumps(event))
    changed["toolInput"]["content"] = "different"
    changed["tool_input"]["content"] = "different"
    out = run_hook(changed, log)
    assert out["permissionDecision"] == "deny"
    seq = Sequencer(Log(str(log)))
    assert len(seq.state.decision_queue) == 2


# ---------------------------------------------------------- fail closed

def test_unmapped_tool_fails_closed():
    result = hook.decide({"toolName": "SomeFutureTool", "toolInput": {}},
                         "/tmp/unused-kernel.jsonl")
    assert result["decision"] == "deny"
    assert result["reason"].startswith("adapter error:")


def test_malformed_stdin_fails_closed(tmp_path):
    log = tmp_path / "kernel.jsonl"
    env = dict(os.environ, JACQUARD_LOG=str(log))
    proc = subprocess.run([sys.executable, HOOK], input="not json",
                          capture_output=True, text=True, env=env,
                          timeout=60)
    assert proc.returncode == 0
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("adapter error:")


def test_corrupt_kernel_log_fails_closed(tmp_path):
    log = tmp_path / "kernel.jsonl"
    log.write_text("this is not a kernel log\n", encoding="utf-8")
    out = run_hook(fixture("pretooluse-read.json"), log)
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("adapter error:")


# ---------------------------------------------------------- sidecar

def test_latency_sidecar_shape(tmp_path):
    log = tmp_path / "kernel.jsonl"
    run_hook(fixture("pretooluse-read.json"), log)
    run_hook(fixture("pretooluse-write.json"), log)
    sidecar = tmp_path / "kernel.jsonl.latency.jsonl"
    lines = [json.loads(line) for line in
             sidecar.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    for line in lines:
        assert set(line) >= {"ts", "tool", "verdict", "decision_ms"}
        assert isinstance(line["decision_ms"], (int, float))
        assert line["decision_ms"] >= 0
    assert [line["tool"] for line in lines] == ["Read", "Write"]
    assert [line["verdict"] for line in lines] == ["allow", "deny"]
    # The sidecar never carries tool arguments.
    assert "seed.txt" not in sidecar.read_text(encoding="utf-8")
    assert "probe2.txt" not in sidecar.read_text(encoding="utf-8")


# ---------------------------------------------------------- constructed

def test_edit_payload_constructed_to_documented_schema(tmp_path):
    # Constructed payload (labelled): Edit was not exercised in
    # the capture session; its shape follows the Write pattern
    # ({file_path, old_string, new_string}) from the same tool
    # family. The adapter maps it to agent-write like Write.
    event = {"hookEventName": "PreToolUse", "toolName": "Edit",
             "toolInput": {"file_path": "/tmp/x.py",
                           "old_string": "a", "new_string": "b"},
             "cwd": str(tmp_path)}
    log = tmp_path / "kernel.jsonl"
    out = run_hook(event, log)
    assert out["permissionDecision"] == "deny"
    assert "QUEUED for operator decision" in out["permissionDecisionReason"]
    seq = Sequencer(Log(str(log)))
    (pid,) = list(seq.state.decision_queue)
    body = seq.state.decision_queue[pid]
    assert body["class"] == "agent-write"
