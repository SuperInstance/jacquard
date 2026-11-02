"""Acceptance criterion 4 (design doc 10, section 5).

A zero-shot agent, given only the spec and the exported
dictionary — no design documents, no conversation — composes a
new word: `hold-for-orin-bench`, which holds dispatches while
the Orin bench is running (sense "orin-bench" is true) and
behaves like maybe-dispatch otherwise.

The agent's submission is recorded, verbatim, in
zeroshot/submission.json (see zeroshot/TASK.md for the exact
brief it received). This test verifies the submission against
the kernel. The criterion passes if the definition is accepted
and behaves as specified, or if the submission records a named,
fixable refusal from the agent's own attempt.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "src"))
sys.path.insert(0, os.path.dirname(__file__))

from jacquard import Sequencer, make_envelope  # noqa: E402
import queue_dictionary  # noqa: E402

SUBMISSION = os.path.join(os.path.dirname(__file__), "zeroshot",
                          "submission.json")
KNOWN_REFUSALS = {"FIELD", "SEQ", "PREV", "HASH", "SPEC",
                  "CONSERVATION", "FRAGMENT", "CLASS", "PROVENANCE",
                  "UNDERDECLARED", "EXAMPLE", "UNREACHABLE", "DEAD",
                  "AMBIGUOUS", "NON_TOTAL"}


def _stage(seq, orin_bench):
    for verdict in queue_dictionary.submit_all(seq):
        assert verdict["status"] == "accepted", verdict
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [
            {"verb": "write",
             "args": ["gpu/queue", ["job-1", "job-2"]]},
            {"verb": "write",
             "args": ["gpu/feeder", {"enabled": False}]},
            {"verb": "write", "args": ["gpu/holds", []]}]},
        ["write"], "c4-stage"))
    seq.submit_sense("gpu-foreign", False, "operator")
    seq.submit_sense("orin-bench", orin_bench, "operator")


def test_zero_shot_submission():
    if not os.path.exists(SUBMISSION):
        pytest.skip("zero-shot submission not recorded yet")
    with open(SUBMISSION, encoding="utf-8") as fh:
        submission = json.load(fh)
    if submission.get("definition") is None:
        # The named-refusal outcome: the agent's attempt failed
        # with a refusal it could name and describe how to fix.
        assert submission.get("refusal") in KNOWN_REFUSALS, submission
        assert submission.get("fix"), submission
        return
    definition = submission["definition"]
    assert definition["name"] == "hold-for-orin-bench"
    # First-try acceptance is the strong outcome. A refusal the
    # kernel names is the criterion's other passing outcome; the
    # builder's log records which one occurred.
    seq = Sequencer()
    _stage(seq, orin_bench=True)
    verdict = seq.submit(make_envelope(
        "zero-shot-agent", "definition", definition,
        definition.get("declared_effects", []), "c4-submit"))
    if verdict["status"] == "REFUSED":
        assert verdict["refusal"] in KNOWN_REFUSALS, verdict
        print("zero-shot outcome: named refusal %s" % verdict["refusal"])
        return
    _stack, requests = seq.evaluate_word("hold-for-orin-bench",
                                         "zero-shot-agent")
    _stack, requests = seq.evaluate_word("hold-for-orin-bench",
                                         "zero-shot-agent")
    assert "dispatch" not in [r["verb"] for r in requests], requests
    seq2 = Sequencer()
    _stage(seq2, orin_bench=False)
    verdict2 = seq2.submit(make_envelope(
        "zero-shot-agent", "definition", definition,
        definition.get("declared_effects", []), "c4-submit"))
    assert verdict2["status"] == "accepted", verdict2
    _stack, requests2 = seq2.evaluate_word("hold-for-orin-bench",
                                          "zero-shot-agent")
    assert "dispatch" in [r["verb"] for r in requests2], requests2
