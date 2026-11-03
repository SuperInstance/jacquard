"""Slice 24 acceptance on the REAL logs (spec 15.3, erratum 2).

The gpu-queue live log was born after the anchor-key rotation
and is signed only by the successor key; under the /1 registry
grammar no registry could schedule it (the retired key names
it in neither map, and an empty window was inexpressible), so
at v1.0.0 it verified only in explicit-key form. Under the /2
grammar the published registry schedules it, and the
pre-rotation proof log still verifies under the same registry.

Fixtures: the vendored witness copies in
tests/data/anchor-registry/ (see PROVENANCE.md there); the
logs are the committed evidence copies under docs/.
"""
import copy
import hashlib
import json
import os

from jacquard.anchor import (load_checkpoints, load_entries,
                             load_key_registry, log_id_of,
                             schedule_from_registry, verify_entries)

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data", "anchor-registry")
GPU_LOG_PATH = os.path.join(HERE, "..", "docs", "slice22",
                            "kernel.jsonl")
PROOF_LOG_PATH = os.path.join(HERE, "..", "docs", "proof-run-2",
                              "kernel.jsonl")
GPU_LOG_SHA256 = ("a0fa08c752de43c515ba9f8ec09fa26605d56e65f8"
                  "cb9cc059a101fb06efd4a2")
PROOF_LOG_SHA256 = ("61d96a2a4d223f4f97e3b6bd6235c3d9cc910ce9c"
                    "dd71f3c4cb0309bad1e3e3c")


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _verify(log_path):
    entries = load_entries(log_path)
    envelopes, problems = load_checkpoints(
        os.path.join(DATA, "checkpoints"))
    assert not problems
    registry = load_key_registry(os.path.join(DATA, "keys.json"))
    schedule = schedule_from_registry(registry, log_id_of(entries))
    return verify_entries(entries, envelopes, schedule[0][1],
                          schedule=schedule)


def test_gpu_live_log_verifies_via_registry():
    assert _sha256(GPU_LOG_PATH) == GPU_LOG_SHA256
    result = _verify(GPU_LOG_PATH)
    assert result["outcome"] == "verified"
    assert result["anchored_length"] == 91
    assert result["unanchored_tail"] == 0
    assert result["checkpoints_checked"] == 2


def test_proof_log_verifies_via_registry():
    assert _sha256(PROOF_LOG_PATH) == PROOF_LOG_SHA256
    result = _verify(PROOF_LOG_PATH)
    assert result["outcome"] == "verified"
    assert result["anchored_length"] == 507
    assert result["unanchored_tail"] == 0
    assert result["checkpoints_checked"] == 3


def test_window_claim_outside_truth_fails_by_name():
    # A /2 registry that hands the gpu log's window to the
    # retired key (which never signed it) schedules cleanly --
    # and the section 15.5 procedure refuses at checkpoint 0,
    # naming the envelope binding. The registry describes; it
    # never manufactures acceptance.
    with open(os.path.join(DATA, "keys.json"),
              encoding="utf-8") as fh:
        registry = json.load(fh)
    forged = copy.deepcopy(registry)
    gpu = ("9cbf80c8e820d49a10da9d92b0f18d2770b48d562c8164366"
           "28c881d14abaff1")
    retired, successor = forged["keys"]
    retired["signs_from"][gpu] = 0
    del successor["signs_from"][gpu]
    entries = load_entries(GPU_LOG_PATH)
    envelopes, problems = load_checkpoints(
        os.path.join(DATA, "checkpoints"))
    assert not problems
    schedule = schedule_from_registry(forged, gpu)
    result = verify_entries(entries, envelopes, schedule[0][1],
                            schedule=schedule)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "history"
    assert result["failure"]["detail"] == (
        "checkpoint 0: envelope pubkey is not the pinned key "
        "for its sequence")
