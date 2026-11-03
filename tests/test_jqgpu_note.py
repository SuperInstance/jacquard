"""The jqgpu note verb (Phase 10, slice 29).

Window 2's halt-clear had no verb: the operator edited
queue.json on the Thor and the explanatory note reached the
kernel log by hand (seq 188 of that log). This battery pins
the verb that replaces the improvisation — bridge-level
shape (the same {event, action[, cause][, job_log]} value
the improvised entry used, producer `operator`) and the
CLI end-to-end over a real file log.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "adapters"))

from gpu_queue import GpuQueueBridge  # noqa: E402
from jacquard import Sequencer  # noqa: E402

WINDOW = {"target_jobs": 1, "opens": "test", "closes": "test"}


class NullThor:
    def add_job(self, lane, name, cmd):
        raise AssertionError("note must not touch the Thor")

    def queue_state(self):
        raise AssertionError("note must not touch the Thor")

    def list_text(self):
        raise AssertionError("note must not touch the Thor")


def test_operator_note_shape(tmp_path):
    bridge = GpuQueueBridge(Sequencer(), NullThor(),
                            str(tmp_path / "journal.jsonl"))
    bridge.ensure_kernel("/oracle/live/kernel.jsonl", WINDOW)
    entry = bridge.operator_note(
        "gpuq lane halt cleared by operator",
        "operator cleared meta.halted in queue.json under "
        "queue.lock, changing nothing else",
        cause="job failed to start twice; gpuq halted per "
              "its documented policy",
        job_log="/home/caseydigennaro/gpu-queue/job-logs/x.log")
    assert entry["kind"] == "sense"
    body = entry["body"]
    assert body["name"] == "gpu-operator-note"
    assert body["producer"] == "operator"
    assert body["value"]["event"] == \
        "gpuq lane halt cleared by operator"
    assert body["value"]["action"].startswith(
        "operator cleared meta.halted")
    assert body["value"]["cause"].startswith("job failed")
    assert body["value"]["job_log"].endswith("x.log")
    assert bridge.seq.log.verify_chain()


def test_operator_note_optional_fields_omitted(tmp_path):
    bridge = GpuQueueBridge(Sequencer(), NullThor(),
                            str(tmp_path / "journal.jsonl"))
    bridge.ensure_kernel("/oracle/live/kernel.jsonl", WINDOW)
    entry = bridge.operator_note("window opened",
                                 "operator opened the window")
    assert set(entry["body"]["value"]) == {"event", "action"}


def test_note_cli_end_to_end(tmp_path):
    root = os.path.join(os.path.dirname(__file__), "..")
    tool = os.path.join(root, "tools", "jqgpu.py")
    log = str(tmp_path / "kernel.jsonl")

    def run(*argv):
        proc = subprocess.run(
            [sys.executable, tool, "--log", log] + list(argv),
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    run("init", "--window", json.dumps(WINDOW))
    out = run("note", "--event", "gpuq lane halt cleared",
              "--text", "operator cleared meta.halted",
              "--cause", "two failed starts")
    assert out["note"] == "recorded"
    entries = [json.loads(l) for l in open(log)]
    notes = [e for e in entries if e["kind"] == "sense"
             and e["body"].get("name") == "gpu-operator-note"]
    assert len(notes) == 1
    assert notes[0]["body"]["value"]["cause"] == \
        "two failed starts"
