"""Slice 21: sealed exports (SPEC section 16).

The redacted export verifies against the anchors; the original
still verifies; a tamper with a sealed field is detected. The
real proof-run log is exercised at the end, in the same shape
as the committed live run (docs/slice21/).
"""
import copy
import hashlib
import hmac
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log  # noqa: E402
from jacquard.anchor import (  # noqa: E402
    anchor_entries, generate_key, load_checkpoints, load_entries,
    load_private_key, public_key_hex, verify_entries)
from jacquard.canonical import canonical  # noqa: E402
from jacquard.sealing import (  # noqa: E402
    SealError, build_seals, commitment_for, make_export,
    targets_for_field, verify_export)

REPO = os.path.join(os.path.dirname(__file__), "..")
TRUE_LOG = os.path.join(REPO, "docs", "proof-run-2", "kernel.jsonl")
PASS = "slice21-test-passphrase"
KEY = bytes.fromhex("ab" * 32)


@pytest.fixture()
def key(tmp_path, monkeypatch):
    monkeypatch.setenv("JACQUARD_ANCHOR_PASSPHRASE", PASS)
    path = str(tmp_path / "k.ed25519")
    generate_key(path)
    return load_private_key(path)


def _history(root):
    envelopes, problems = load_checkpoints(str(root))
    assert problems == []
    return envelopes


def _log_with_releases(tmp_path, name="kernel.jsonl"):
    path = str(tmp_path / name)
    log = Log(path=path)
    log.append("decision", {"producer": "agent", "class": "work",
                            "proposal_id": "p1", "outcome": "queued"})
    log.append("decision", {"producer": "agent", "class": "work",
                            "proposal_id": "p1", "outcome": "allow",
                            "releases": "p1", "released_by": "operator"})
    log.append("sense", {"producer": "op", "name": "load", "value": 3})
    return path


def _seal(path, field="released_by", cls="operator-identity",
          mode="hash", key=None):
    entries = load_entries(path)
    targets = targets_for_field(entries, field, cls)
    seals = build_seals(entries, targets, mode=mode, redaction_key=key)
    log = Log(path=path)
    log.append("seal", {"producer": "operator", "seals": seals})
    return load_entries(path)


def _anchored(tmp_path, key, entries, lengths):
    root = tmp_path / "checkpoints"
    for length in lengths:
        anchor_entries(entries, key, "seal-test", str(root),
                       log_length=length)
    return root


# ---------------------------------------------------------------- roundtrip

def test_roundtrip_verified(tmp_path, key):
    path = _log_with_releases(tmp_path)
    entries = _seal(path)
    root = _anchored(tmp_path, key, entries, [len(entries)])
    export = make_export(entries)
    result = verify_export(export, _history(root), public_key_hex(key),
                           original_entries=entries)
    assert result["outcome"] == "verified"
    assert result["seals_applied"] == 1
    assert result["seals_anchored"] is True
    assert result["commitments_checked"] == "full"
    # The sealed VALUE is gone from its position (the class name
    # "operator-identity" remains — classes are disclosed, SPEC 16.1).
    assert b'"released_by":"operator"' not in canonical(
        export["entries"][1]["body"])
    assert export["entries"][1]["body"]["released_by"]["class"] == "operator-identity"
    # The unredacted original still verifies, plain section 15.5.
    plain = verify_entries(entries, _history(root), public_key_hex(key))
    assert plain["outcome"] == "verified"


def test_unanchored_seal_reported(tmp_path, key):
    path = _log_with_releases(tmp_path)
    entries = _seal(path)
    # Anchor only the pre-seal prefix: the seal entry is tail.
    root = _anchored(tmp_path, key, entries, [3])
    export = make_export(entries)
    result = verify_export(export, _history(root), public_key_hex(key))
    assert result["outcome"] == "verified_to_anchor"
    assert result["anchored_length"] == 3
    assert result["unanchored_tail"] == 1
    assert result["seals_anchored"] is False


def test_prefix_slice_export(tmp_path, key):
    path = _log_with_releases(tmp_path)
    entries = _seal(path)
    root = _anchored(tmp_path, key, entries, [2, len(entries)])
    export = make_export(entries, exported_length=2)
    result = verify_export(export, _history(root), public_key_hex(key))
    assert result["outcome"] == "verified"
    assert result["exported_length"] == 2
    assert result["checkpoints_beyond"] == 1


# ------------------------------------------------------------------ tampers

def _verified_export(tmp_path, key):
    path = _log_with_releases(tmp_path)
    entries = _seal(path)
    root = _anchored(tmp_path, key, entries, [len(entries)])
    return make_export(entries), _history(root), public_key_hex(key)


def test_tampered_sealed_field_detected(tmp_path, key):
    export, history, pub = _verified_export(tmp_path, key)
    export = copy.deepcopy(export)
    marker = export["entries"][1]["body"]["released_by"]
    marker["sealed"] = ("0" if marker["sealed"][0] != "0" else "1") \
        + marker["sealed"][1:]
    result = verify_export(export, history, pub)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "seals"
    assert result["failure"]["entry_seq"] == 1


def test_tampered_seal_entry_detected(tmp_path, key):
    export, history, pub = _verified_export(tmp_path, key)
    export = copy.deepcopy(export)
    export["entries"][3]["body"]["seals"][0]["class"] = "other-class"
    result = verify_export(export, history, pub)
    assert result["outcome"] == "failed"


def test_tampered_unsealed_field_detected(tmp_path, key):
    export, history, pub = _verified_export(tmp_path, key)
    export = copy.deepcopy(export)
    export["entries"][2]["body"]["value"] = 99
    result = verify_export(export, history, pub)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "entries"


def test_sealed_value_presented_in_clear_detected(tmp_path, key):
    export, history, pub = _verified_export(tmp_path, key)
    export = copy.deepcopy(export)
    export["entries"][1]["body"]["released_by"] = "operator"
    result = verify_export(export, history, pub)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "seals"


def test_omitted_entry_detected(tmp_path, key):
    export, history, pub = _verified_export(tmp_path, key)
    export = copy.deepcopy(export)
    del export["entries"][2]
    export["exported_length"] = 3
    result = verify_export(export, history, pub)
    assert result["outcome"] == "failed"


def test_wrong_commitment_in_seal_detected_with_original(tmp_path, key):
    # A seal computed over the WRONG value passes consistency but
    # fails the moment the original is supplied (SPEC 16.1).
    path = _log_with_releases(tmp_path)
    entries = load_entries(path)
    seals = [{"entry_seq": 1, "field": "released_by",
              "class": "operator-identity", "mode": "hash",
              "commitment": commitment_for(1, "released_by", "mallory",
                                           "hash")}]
    log = Log(path=path)
    log.append("seal", {"producer": "operator", "seals": seals})
    entries = load_entries(path)
    root = _anchored(tmp_path, key, entries, [len(entries)])
    export = make_export(entries)
    result = verify_export(export, _history(root), public_key_hex(key))
    assert result["outcome"] == "verified"
    assert result["commitments_checked"] == "consistency"
    result = verify_export(export, _history(root), public_key_hex(key),
                           original_entries=entries)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "commitment"


# -------------------------------------------------------------------- keyed

def test_keyed_commitment_resists_dictionary(tmp_path, key):
    path = _log_with_releases(tmp_path)
    entries = _seal(path, mode="keyed", key=KEY)
    seal = entries[3]["body"]["seals"][0]
    # Enumerate plausible values the hash-mode way: none matches,
    # because the keyed commitment is an HMAC under the key.
    for candidate in ("operator", "alice", "admin", "root"):
        guess = commitment_for(1, "released_by", candidate, "hash")
        assert guess != seal["commitment"]
    root = _anchored(tmp_path, key, entries, [len(entries)])
    export = make_export(entries)
    result = verify_export(export, _history(root), public_key_hex(key),
                           original_entries=entries)
    assert result["outcome"] == "verified"
    assert result["commitments_checked"] == "consistency"
    result = verify_export(export, _history(root), public_key_hex(key),
                           original_entries=entries, redaction_key=KEY)
    assert result["outcome"] == "verified"
    assert result["commitments_checked"] == "keyed"


# ------------------------------------------------------------------ refusals

def test_seal_refusals(tmp_path):
    path = _log_with_releases(tmp_path)
    entries = _seal(path)
    with pytest.raises(SealError):
        build_seals(entries, [(3, "seals", "x")])  # a seal entry
    with pytest.raises(SealError):
        build_seals(entries, [(99, "released_by", "x")])  # no such entry
    with pytest.raises(SealError):
        build_seals(entries, [(1, "no_such_field", "x")])


# --------------------------------------------------------------- the real log

def test_proof_run_log_sealed_export(tmp_path, key):
    """The live-run shape: seal entries appended to a working
    copy of the frozen proof log; the export verifies against
    the anchors, and so does the unredacted working log."""
    import shutil
    working = str(tmp_path / "working.jsonl")
    shutil.copy(TRUE_LOG, working)
    entries = load_entries(working)
    targets = targets_for_field(entries, "released_by",
                                "operator-identity") \
        + targets_for_field(entries, "rejected_by", "operator-identity")
    assert len(targets) == 27
    seals = build_seals(entries, targets)
    log = Log(path=working)
    log.append("seal", {"producer": "operator", "seals": seals})
    entries = load_entries(working)
    assert len(entries) == 508
    root = tmp_path / "checkpoints"
    anchor_entries(entries, key, "proof-run-2/kernel", str(root),
                   log_length=250)
    anchor_entries(entries, key, "proof-run-2/kernel", str(root),
                   log_length=507)
    history = _history(root)
    export = make_export(entries)
    result = verify_export(export, history, public_key_hex(key),
                           original_entries=entries)
    assert result["outcome"] == "verified_to_anchor"
    assert result["anchored_length"] == 507
    assert result["unanchored_tail"] == 1
    assert result["seals_applied"] == 27
    assert result["seals_anchored"] is False
    assert result["commitments_checked"] == "full"
    # The frozen original still verifies against the same history.
    frozen = load_entries(TRUE_LOG)
    plain = verify_entries(frozen, history, public_key_hex(key))
    assert plain["outcome"] == "verified"
    # Anchor the seal entry too: now the export verifies fully.
    anchor_entries(entries, key, "proof-run-2/kernel", str(root))
    history = _history(root)
    result = verify_export(export, history, public_key_hex(key))
    assert result["outcome"] == "verified"
    assert result["seals_anchored"] is True
    # And the sealed values do not appear at the sealed positions.
    blob = canonical(export["entries"][100]["body"])
    assert b'"released_by":"operator"' not in blob
