"""Acceptance criterion 3 (design doc 10, section 5).

The feeder-churn reading — a producer whose outputs are never
used — is computed from the record alone, by the generic records
projection, with no churn-specific code. The feeder numbers come
from the real dataset: 1,635 feeder jobs in queue.json, each
producing 8 asset outputs (the daemon's family count), and no
recorded use of any of them anywhere in the log.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "src"))

from jacquard import Sequencer, make_envelope  # noqa: E402
from jacquard.records import output_use_ratio, outputs_and_uses  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..",
                    "tests", "data", "gpu-queue")
ASSETS_PER_FEEDER_JOB = 8


def feeder_job_ids():
    with open(os.path.join(DATA, "queue.json"), encoding="utf-8") as fh:
        queue = json.load(fh)
    return [j["id"] for j in queue["jobs"] if j["kind"] == "feeder"]


def build_feeder_record():
    """The foundry-loop producer record, rebuilt from the real
    queue: one executed write per feeder job, carrying its 8
    output ids. Batched 100 jobs per proposal for speed; the
    records projection is insensitive to batching."""
    seq = Sequencer()
    ids = feeder_job_ids()
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        requests = []
        for job_id in batch:
            outputs = ["%s-asset-%d" % (job_id, n)
                       for n in range(ASSETS_PER_FEEDER_JOB)]
            requests.append({
                "verb": "write",
                "args": ["foundry/latest", {"job": job_id}],
                "outputs": outputs})
        verdict = seq.submit(make_envelope(
            "foundry-loop", "proposal", {"requests": requests},
            ["write"], "feeder-batch-%d" % start))
        assert verdict["outcome"] == "allow"
    return seq


def test_feeder_output_use_is_zero_from_records_alone():
    ids = feeder_job_ids()
    assert len(ids) == 1635
    seq = build_feeder_record()
    outputs, uses = outputs_and_uses(seq.log.entries, "foundry-loop")
    assert outputs == len(ids) * ASSETS_PER_FEEDER_JOB == 13080
    assert uses == 0
    assert output_use_ratio(seq.log.entries, "foundry-loop") == 0.0


def test_projection_is_not_a_hardcoded_zero():
    seq = Sequencer()
    seq.submit(make_envelope(
        "maker", "proposal",
        {"requests": [{"verb": "write", "args": ["a", 1],
                       "outputs": ["o-1"]},
                      {"verb": "write", "args": ["b", 2],
                       "outputs": ["o-2"]}]},
        ["write"], "toy-1"))
    seq.submit(make_envelope(
        "reader", "proposal",
        {"requests": [{"verb": "write", "args": ["scene", ["o-1"]]}],
         "uses": ["o-1"]},
        ["write"], "toy-2"))
    assert output_use_ratio(seq.log.entries, "maker") == 0.5
