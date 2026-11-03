"""The jq submit verb (Phase 13, slice 37).

The outside test's Run 4 found the operator CLI had no way
to submit an arbitrary item: subcommands were seed-demo,
queue, status, decide, execute, replay, so the batched-
approvals flow could not be driven end-to-end for a user's
own proposals. This battery pins the verb that closes the
gap — and the cross-process idempotency it must carry,
because the kernel's verdict cache is per-process: a fresh
CLI invocation consults the folded record, prints the
recorded verdict for a duplicate, and changes nothing (a
queued duplicate previously raised an unhandled Refusal
from machine-instance creation; an allowed duplicate was
silently re-decided and re-executed).

Drives tools/jq.py as a subprocess, like test_cli.py.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log, Sequencer  # noqa: E402
from jacquard.present import binding_hash  # noqa: E402

JQ = os.path.join(os.path.dirname(__file__), "..", "tools", "jq.py")

NOTIFY = {"producer": "ops-bot", "id": "n1",
          "declared_effects": ["notify"],
          "body": {"class": "ops", "requests": [
              {"verb": "notify", "args": ["ops", "hello"]}]}}

DISPATCH = {"producer": "ops-bot", "id": "d1",
            "declared_effects": ["dispatch"],
            "body": {"class": "ops", "requests": [
                {"verb": "dispatch", "args": [{
                    "cmd": ["python3", "-c", "print('submitted-ran')"],
                    "compensate": ["python3", "-c", "print('undone')"],
                }]}]}}

UNDERDECLARED = {"producer": "ops-bot", "id": "u1",
                 "declared_effects": [],
                 "body": {"requests": [
                     {"verb": "notify", "args": ["ops", "sneaky"]}]}}


def run_cli(log, *argv, expect=0, stdin=None):
    proc = subprocess.run(
        [sys.executable, JQ, "--log", str(log)] + list(argv),
        capture_output=True, text=True, input=stdin)
    assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
    return proc.stdout


def write_proposal(tmp_path, name, spec):
    path = tmp_path / name
    path.write_text(json.dumps(spec), encoding="utf-8")
    return str(path)


def entries(log):
    return Sequencer(Log(str(log))).log.entries


def test_submit_notify_queues_then_batch_decide_executes(tmp_path):
    log = tmp_path / "kernel.jsonl"
    prop = write_proposal(tmp_path, "n1.json", NOTIFY)
    verdict = json.loads(run_cli(log, "submit", prop))
    assert verdict["status"] == "decided"
    assert verdict["outcome"] == "queue"
    assert verdict["reasons"] == ["protected-effect:notify"]
    pid = verdict["proposal_id"]

    out = run_cli(log, "queue")
    assert pid in out  # the submitted item is presented for decision

    seq = Sequencer(Log(str(log)))
    out = run_cli(log, "decide", "approve", pid,
                  "--hash", binding_hash(seq, pid))
    assert "approved %s" % pid in out
    seq = Sequencer(Log(str(log)))
    executions = [e["body"] for e in seq.log.entries
                  if e["kind"] == "execution"]
    assert any(e["proposal_id"] == pid for e in executions)
    out = run_cli(log, "replay", pid)
    assert "final proposal state: closed" in out


def test_submit_dispatch_auto_decides_and_executes(tmp_path):
    log = tmp_path / "kernel.jsonl"
    prop = write_proposal(tmp_path, "d1.json", DISPATCH)
    verdict = json.loads(run_cli(log, "submit", prop))
    assert verdict["outcome"] == "allow"
    out = run_cli(log, "execute")
    assert "exit 0" in out
    seq = Sequencer(Log(str(log)))
    action_id = verdict["proposal_id"] + "/action-0"
    assert seq.machine_instance_state(action_id) == "confirmed"


def test_submit_from_stdin(tmp_path):
    log = tmp_path / "kernel.jsonl"
    verdict = json.loads(run_cli(log, "submit", "-",
                                 stdin=json.dumps(NOTIFY)))
    assert verdict["outcome"] == "queue"


def test_submit_duplicate_replays_recorded_verdict(tmp_path):
    log = tmp_path / "kernel.jsonl"
    prop = write_proposal(tmp_path, "n1.json", NOTIFY)
    first = json.loads(run_cli(log, "submit", prop))
    before = entries(log)
    second = json.loads(run_cli(log, "submit", prop))
    assert second["proposal_id"] == first["proposal_id"]
    assert second["outcome"] == "queue"
    assert second["duplicate"] is True
    assert entries(log) == before  # nothing appended, nothing re-decided


def test_submit_duplicate_of_allowed_does_not_reexecute(tmp_path):
    log = tmp_path / "kernel.jsonl"
    prop = write_proposal(tmp_path, "d1.json", DISPATCH)
    json.loads(run_cli(log, "submit", prop))
    before = entries(log)
    second = json.loads(run_cli(log, "submit", prop))
    assert second["outcome"] == "allow" and second["duplicate"] is True
    assert entries(log) == before


def test_submit_underdeclared_refused_and_duplicate_refused(tmp_path):
    log = tmp_path / "kernel.jsonl"
    prop = write_proposal(tmp_path, "u1.json", UNDERDECLARED)
    verdict = json.loads(run_cli(log, "submit", prop, expect=1))
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"
    before = entries(log)
    again = json.loads(run_cli(log, "submit", prop, expect=1))
    assert again["refusal"] == "UNDERDECLARED"
    assert again["duplicate"] is True
    assert entries(log) == before


def test_submit_malformed_leaves_no_trace(tmp_path):
    log = tmp_path / "kernel.jsonl"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    out = run_cli(log, "submit", str(bad), expect=1)
    assert "FAIL submit" in out
    missing = tmp_path / "missing.json"
    spec = {"producer": "ops-bot", "declared_effects": ["notify"],
            "body": {"requests": []}}
    missing.write_text(json.dumps(spec), encoding="utf-8")
    out = run_cli(log, "submit", str(missing), expect=1)
    assert "missing field: id" in out
    assert not log.exists()  # validation happens before any kernel write
