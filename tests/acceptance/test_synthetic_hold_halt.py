"""Reconstructed fixtures: the hold and the two-failure halt.

RECONSTRUCTED — the real gpu-queue record (2026-10-27/28)
contains no holds, no failures, and no halt, so these branches
of the successor rule cannot be replayed from data. The
scenarios in tests/data/synthetic/ are derived line-by-line
from the daemon source (daemon.py, copied with the dataset) and
are marked as reconstructions in the fixture files themselves.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "src"))
sys.path.insert(0, os.path.dirname(__file__))

from jacquard import Sequencer, make_envelope  # noqa: E402
import queue_dictionary  # noqa: E402

SYNTHETIC = os.path.join(os.path.dirname(__file__), "..", "..",
                         "tests", "data", "synthetic")


def _write(seq, unit, value, idem):
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": [unit, value]}]},
        ["write"], idem))


def _execute_requests(seq, requests, idem):
    effects = sorted({r["verb"] for r in requests})
    seq.submit(make_envelope(
        "gpu-queue-daemon", "proposal", {"requests": requests},
        effects, idem))


def run_scenario(name):
    with open(os.path.join(SYNTHETIC, name), encoding="utf-8") as fh:
        scenario = json.load(fh)
    assert scenario["reconstructed"] is True
    seq = Sequencer()
    for verdict in queue_dictionary.submit_all(seq):
        assert verdict["status"] == "accepted", verdict
    for i, step in enumerate(scenario["steps"]):
        idem = "%s-%d" % (name, i)
        if "set_unit" in step:
            unit, value = step["set_unit"]
            _write(seq, unit, value, idem)
        elif "set_sense" in step:
            sense, value = step["set_sense"]
            seq.submit_sense(sense, value, "operator")
        elif "eval_expect" in step:
            word, verbs = step["eval_expect"]
            _stack, requests = seq.evaluate_word(word, "operator")
            assert [r["verb"] for r in requests] == verbs, (name, step)
        elif "eval_exec" in step:
            (word,) = step["eval_exec"]
            _stack, requests = seq.evaluate_word(word, "operator")
            if requests:
                _execute_requests(seq, requests, idem)
        elif "assert_unit" in step:
            unit, value = step["assert_unit"]
            assert seq.state.units.get(unit) == value, (name, step)
        elif "assert_unit_absent" in step:
            (unit,) = step["assert_unit_absent"]
            assert unit not in seq.state.units, (name, step)
        else:
            raise AssertionError("unknown step %r" % (step,))
    return seq


def test_hold_branch_reconstructed():
    seq = run_scenario("hold_case.json")
    assert seq.state.units["gpu/holds"] == ["solo-1"]


def test_two_failure_halt_reconstructed():
    seq = run_scenario("halt_case.json")
    assert seq.state.units["gpu/halted"] is True
    assert seq.state.units["gpu/start-failures"] == 2
