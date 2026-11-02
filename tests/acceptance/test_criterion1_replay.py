"""Acceptance criterion 1 (design doc 10, section 5).

The gpu-queue successor rule is expressed as dictionary
definitions with zero imperative policy code, and replaying the
real Thor gpu-queue record through the kernel reproduces the
recorded dispatch order exactly.

Disclosures (tests/data/gpu-queue/PROVENANCE.md): the real
record contains no holds and no halts — those branches are
covered by reconstructed fixtures in test_synthetic_hold_halt.py.
The feeder-enabled state and the foreign-work sense during the
run are reconstructed from the daemon's behaviour, as documented.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "src"))

from replay_gpu_queue import load_record, run_replay  # noqa: E402


def test_record_is_serial_and_complete():
    job_ids, events = load_record()
    assert len(job_ids) == 1637
    dispatches = [e for e in events if e["event"] == "dispatch"]
    finishes = [e for e in events if e["event"] == "finish"]
    assert len(dispatches) == len(finishes) == 1637
    # Strictly alternating dispatch/finish: never two jobs running.
    kinds = [e["event"] for e in events]
    assert kinds == ["dispatch", "finish"] * 1637
    assert all(e.get("exit") == 0 for e in finishes)


def test_replay_reproduces_the_record():
    job_ids, events = load_record()
    recorded = [e["job"] for e in events if e["event"] == "dispatch"]
    assert recorded == job_ids
    report = run_replay()
    assert report["dispatched"] == recorded
    assert report["holds"] == []
    assert report["evaluations"] == 1637
    assert report["chain_ok"]
