"""The executor battery (SPEC section 10.5): dispatch -> confirm,
dispatch -> fail -> compensate, and duplicate delivery with no
double effect. Runs against the subprocess sandbox everywhere;
the bwrap sandbox is exercised additionally where installed
(the Oracle has it).
"""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "adapters"))

from executor import SandboxedExecutor  # noqa: E402
from jacquard import Sequencer, install_lifecycles, make_envelope  # noqa: E402


def kernel_with_dispatch(tmp_path, payload, ident="ex-1"):
    seq = Sequencer()
    install_lifecycles(seq)
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "dispatch", "args": [payload]}]},
        ["dispatch"], ident))
    action_id = verdict["proposal_id"] + "/action-0"
    assert seq.machine_instance_state(action_id) == "dispatched"
    return seq, action_id


def test_dispatch_confirm(tmp_path):
    seq, action_id = kernel_with_dispatch(
        tmp_path, {"cmd": ["python3", "-c", "print('ran-ok')"]})
    executor = SandboxedExecutor(seq, str(tmp_path / "journal.jsonl"),
                                 sandbox="subprocess")
    records = executor.run_once()
    assert records[0]["exit"] == 0
    assert "ran-ok" in records[0]["stdout"]
    assert seq.machine_instance_state(action_id) == "confirmed"


def test_dispatch_fail_then_compensate(tmp_path):
    seq, action_id = kernel_with_dispatch(tmp_path, {
        "cmd": ["python3", "-c", "import sys; sys.exit(3)"],
        "compensate": ["python3", "-c", "print('undone')"]})
    executor = SandboxedExecutor(seq, str(tmp_path / "journal.jsonl"),
                                 sandbox="subprocess")
    records = executor.run_once()
    assert records[0]["exit"] == 3
    assert seq.machine_instance_state(action_id) == "compensated"
    with open(tmp_path / "journal.jsonl", encoding="utf-8") as fh:
        journal = [json.loads(line) for line in fh]
    compensation = [r for r in journal
                    if r["action_id"] == action_id + ":compensate"]
    assert compensation and "undone" in compensation[0]["stdout"]


def test_duplicate_delivery_has_no_double_effect(tmp_path):
    marker = tmp_path / "marker.txt"
    script = ("import sys; "
              "open(sys.argv[1], 'a').write('x\\n')")
    payload = {"cmd": ["python3", "-c", script, str(marker)]}
    # the subprocess sandbox scrubs cwd, not absolute paths; the
    # marker lives outside the sandbox scratch dir by design of
    # this test (the sandbox mode under test is the fallback).
    seq, action_id = kernel_with_dispatch(tmp_path, payload)
    journal = str(tmp_path / "journal.jsonl")
    first = SandboxedExecutor(seq, journal, sandbox="subprocess")
    first.run_once()
    assert seq.machine_instance_state(action_id) == "confirmed"
    # duplicate delivery: a fresh executor over the same journal
    # (a restart) must not re-run the command.
    second = SandboxedExecutor(seq, journal, sandbox="subprocess")
    record = second.deliver(action_id, payload)
    assert record["exit"] == 0
    with open(marker, encoding="utf-8") as fh:
        assert fh.read() == "x\n"  # ran exactly once


def test_bad_payload_fails_without_running(tmp_path):
    seq, action_id = kernel_with_dispatch(tmp_path, {"note": "no cmd"})
    executor = SandboxedExecutor(seq, str(tmp_path / "journal.jsonl"),
                                 sandbox="subprocess")
    records = executor.run_once()
    assert records[0]["exit"] is None
    assert seq.machine_instance_state(action_id) == "failed"


@pytest.mark.skipif(shutil.which("bwrap") is None,
                    reason="bubblewrap not installed on this machine")
def test_bwrap_sandbox_isolates_the_filesystem(tmp_path):
    # the command tries to write outside its tmpfs and read a
    # host path; under bwrap the write goes to the sandbox tmpfs
    # (invisible afterwards) and the run still confirms.
    seq, action_id = kernel_with_dispatch(tmp_path, {
        "cmd": ["python3", "-c",
                "open('/tmp/inside.txt', 'w').write('x'); print('done')"]})
    executor = SandboxedExecutor(seq, str(tmp_path / "journal.jsonl"),
                                 sandbox="bwrap")
    records = executor.run_once()
    assert records[0]["sandbox"] == "bwrap"
    assert records[0]["exit"] == 0
    assert seq.machine_instance_state(action_id) == "confirmed"
    assert not os.path.exists("/tmp/inside.txt")
