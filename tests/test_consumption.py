"""Consumption policy v2 (Phase 10, slice 27).

Unit coverage of adapters/consumption.py on synthetic log
entries (completed-consumption-only ratios; the promise-
flattery regression; the exemption budget and its claims),
plus the frozen-evidence re-score: the two live windows'
log (docs/slice25/kernel.jsonl) repriced under v2 must
reproduce the deltas recorded in
docs/slice27-consumption-policy-v2.md — most importantly
bench-7, invisible to v1 at a promise-flattered 6667 bp,
held by v2 at 3333 bp with a wasted-work classification.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "adapters"))

from consumption import load_names, price_one, price_stream  # noqa: E402

CLS = "gpu-heavy"


def _decision(seq, pid, producer, outcome="allow"):
    return {"seq": seq, "kind": "decision",
            "body": {"class": CLS, "proposal_id": pid,
                     "producer": producer, "outcome": outcome}}


def _execution(seq, pid, outputs=(), uses=()):
    item = {"verb": "dispatch", "args": [{}]}
    if outputs:
        item["outputs"] = list(outputs)
    return {"seq": seq, "kind": "execution",
            "body": {"proposal_id": pid, "applied": [item],
                     "uses": list(uses)}}


def _outcome(seq, pid, status="completed"):
    return {"seq": seq, "kind": "sense",
            "body": {"name": "gpu-outcome",
                     "value": {"action_id": pid + "/action-0",
                               "status": status}}}


def _history_with_consumer(consumer_status):
    """Producer p: three completed outputs; a consumer job
    declared a use of one of them, with the given fate."""
    entries = [
        _decision(1, "a", "p"), _execution(2, "a", ["o1"]),
        _outcome(3, "a"),
        _decision(4, "b", "p"), _execution(5, "b", ["o2"]),
        _outcome(6, "b"),
        _decision(7, "c", "p"), _execution(8, "c", ["o3"]),
        _outcome(9, "c"),
        _decision(10, "u", "q"), _execution(11, "u", ["x"],
                                           uses=["o1"]),
    ]
    if consumer_status is not None:
        entries.append(_outcome(12, "u", consumer_status))
    return entries


def test_completed_consumption_counts():
    entries = _history_with_consumer("completed")
    got = price_one(entries, CLS, "p", "o4")
    assert got["completed_outputs"] == 3
    assert got["ratio_bp"] == 3333
    assert got["would_hold"] is True


def test_declared_but_incomplete_consumption_does_not_count():
    # the promise-flattery regression: the consumer declared
    # the use but has not completed at pricing time
    entries = _history_with_consumer(None)
    got = price_one(entries, CLS, "p", "o4")
    assert got["ratio_bp"] == 0
    assert got["would_hold"] is True


def test_failed_consumer_does_not_count():
    entries = _history_with_consumer("failed")
    got = price_one(entries, CLS, "p", "o4")
    assert got["ratio_bp"] == 0
    assert got["would_hold"] is True


def test_exemption_budget_and_claims():
    # two completed outputs: inside the budget of 3 — exempt
    # even at ratio 0, and the exemption is a recorded claim
    entries = [
        _decision(1, "a", "p"), _execution(2, "a", ["o1"]),
        _outcome(3, "a"),
        _decision(4, "b", "p"), _execution(5, "b", ["o2"]),
        _outcome(6, "b"),
        _decision(7, "c", "p"), _execution(8, "c", ["o3"]),
    ]
    got = price_one(entries, CLS, "p", "o3")
    assert got["budget_exempt"] is True
    assert got["exemption_claimed"] is True
    assert got["would_hold"] is False
    rows, claims = price_stream(entries, CLS)
    assert claims.get("p") == 3  # a, b, c each spent a claim


def test_declared_consumer_blocks_hold():
    entries = _history_with_consumer("completed")
    entries.append(_execution(13, "z", [], uses=["o4"]))
    got = price_one(entries, CLS, "p", "o4")
    assert got["has_declared_consumer"] is True
    assert got["would_hold"] is False


def test_frozen_windows_rescore():
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "docs", "slice25", "kernel.jsonl")
    entries = [json.loads(l) for l in open(path)]
    names = load_names(entries, path + ".gpu-journal.jsonl")
    rows, claims = price_stream(entries, "gpu-bench", names)
    by_name = {r["name"]: r for r in rows}
    bench7 = by_name["jacquard-bench-7"]
    assert bench7["trailing_ratio_bp"] == 3333  # v1 said 6667
    assert bench7["would_hold"] is True
    assert bench7["classification"] == \
        "true-positive (wasted work)"
    assert bench7["would_hold_refined"] is False
    holds = [r for r in rows if r["would_hold"]]
    assert len(holds) == 6
    assert sum(1 for r in holds
               if r["classification"].startswith("true")) == 5
    assert sum(1 for r in holds
               if r["classification"] == "false-positive") == 0
    assert claims == {"jacquard-build": 4}
