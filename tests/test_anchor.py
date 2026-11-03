"""Slice 18: chain-head anchoring (SPEC section 15).

Both directions are asserted against the committed forged fixture
(tests/data/forged/, see its PROVENANCE.md): the forged log —
one decision outcome flipped at seq 100, the hash chain recomputed
from there — passes the kernel's internal chain verification, and
anchor verification FAILS on it naming the first divergent
checkpoint. The true frozen proof log verifies; extension and
truncation report exactly as section 15.5 states.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log  # noqa: E402
from jacquard.anchor import (  # noqa: E402
    AnchorError, anchor_entries, generate_key, head_at, load_checkpoints,
    load_entries, load_private_key, log_id_of, public_key_hex,
    verify_entries, verify_internal_chain)

REPO = os.path.join(os.path.dirname(__file__), "..")
TRUE_LOG = os.path.join(REPO, "docs", "proof-run-2", "kernel.jsonl")
FORGED_LOG = os.path.join(REPO, "tests", "data", "forged",
                          "proof-run-2-forged.jsonl")
JQANCHOR = os.path.join(REPO, "tools", "jqanchor.py")
TRUE_HEAD_250 = "9a3f33a27ecb5c2e77b59131672675379816a92a6221b5d1d8e821be808bb076"
TRUE_HEAD_507 = "1e02bd867b777e165189d1adc0cc3a21227400ca2ee916003d38ce630740c8d5"


TEST_PASSPHRASE = "slice21-test-passphrase"


@pytest.fixture()
def key_path(tmp_path, monkeypatch):
    # Spec 0.6: keygen requires a passphrase (here via the
    # environment variable, the documented run-time channel).
    monkeypatch.setenv("JACQUARD_ANCHOR_PASSPHRASE", TEST_PASSPHRASE)
    path = str(tmp_path / "anchor-key.ed25519")
    generate_key(path)
    return path


@pytest.fixture()
def small_log(tmp_path):
    path = str(tmp_path / "kernel.jsonl")
    log = Log(path=path)
    for i in range(6):
        log.append("sense", {"producer": "op", "name": "s%d" % i,
                             "value": i})
    return path


def _anchor(entries, key, label, root, length=None):
    return anchor_entries(entries, key, label, str(root),
                          log_length=length)


def _history(root):
    envelopes, problems = load_checkpoints(str(root))
    assert problems == []
    return envelopes


# ------------------------------------------------------------- keys

def test_keygen_refuses_overwrite(key_path):
    with pytest.raises(AnchorError):
        generate_key(key_path)


def test_keygen_mode_and_location(key_path):
    assert os.stat(key_path).st_mode & 0o777 == 0o600
    assert load_private_key(key_path) is not None


def test_keygen_refuses_repo_path(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(AnchorError):
        generate_key(str(tmp_path / "key.ed25519"),
                     passphrase=TEST_PASSPHRASE)


def test_kernel_import_does_not_require_cryptography():
    # anchor.py is the only module needing `cryptography`; the
    # kernel package must import in a fresh interpreter without
    # pulling in the anchor module or that package.
    src = os.path.join(REPO, "src")
    code = ("import sys; sys.path.insert(0, %r); import jacquard; "
            "assert 'jacquard.anchor' not in sys.modules; "
            "assert 'cryptography' not in sys.modules; "
            "print('clean')" % src)
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "clean"


# ------------------------------------------------- roundtrip outcomes

def test_small_log_full_anchor_verifies(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root, length=3)
    _anchor(entries, key, "small", root)
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "verified"
    assert result["anchored_length"] == 6
    assert result["unanchored_tail"] == 0
    assert result["checkpoints_checked"] == 2
    assert result["internal_chain_ok"] is True


def test_tail_reported_exactly(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root, length=3)
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "verified_to_anchor"
    assert result["anchored_length"] == 3
    assert result["unanchored_tail"] == 3


def test_extension_is_tail_not_forgery(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root)
    log = Log(path=small_log)  # reopens + verifies the 0.5 chain
    log.append("sense", {"producer": "op", "name": "extra", "value": 99})
    log.append("sense", {"producer": "op", "name": "extra2", "value": 100})
    extended = load_entries(small_log)
    assert verify_internal_chain(extended)
    result = verify_entries(extended, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "verified_to_anchor"
    assert result["anchored_length"] == 6
    assert result["unanchored_tail"] == 2


def test_unanchored_is_not_failed(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    result = verify_entries(entries, [], public_key_hex(key))
    assert result["outcome"] == "unanchored"
    assert result["anchored_length"] == 0
    assert result["unanchored_tail"] == 6


def test_truncation_below_anchor_fails(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root)  # anchors length 6
    result = verify_entries(entries[:4], _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "prefix"
    assert result["failure"]["checkpoint_seq"] == 0
    # The reported lengths stay arithmetically consistent even
    # on failure: tail == log_length - anchored_length (the
    # failure happened at the first checkpoint, so nothing is
    # counted anchored).
    assert result["anchored_length"] == 0
    assert result["unanchored_tail"] == 4
    assert result["log_length"] - result["anchored_length"] \
        == result["unanchored_tail"]


def test_anchor_refuses_backwards_and_broken(tmp_path, key_path,
                                             small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root, length=5)
    with pytest.raises(AnchorError):
        _anchor(entries, key, "small", root, length=2)
    broken = [dict(e) for e in entries]
    broken[2] = dict(broken[2], body={"producer": "op", "name": "x",
                                      "value": -1})
    with pytest.raises(AnchorError):
        _anchor(broken, key, "small", tmp_path / "other")


# ---------------------------------------------------- history attacks

def test_wrong_pinned_key_fails_history(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root)
    other = str(tmp_path / "other-key")
    generate_key(other, passphrase=TEST_PASSPHRASE)
    wrong = public_key_hex(load_private_key(other))
    result = verify_entries(entries, _history(root), wrong)
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "history"
    assert result["failure"]["checkpoint_seq"] == 0


def test_dropped_checkpoint_breaks_history_chain(tmp_path, key_path,
                                                 small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root, length=2)
    _anchor(entries, key, "small", root, length=4)
    _anchor(entries, key, "small", root)
    os.remove(root / log_id_of(entries) / "000001.json")
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "history"


def test_tampered_signature_fails_history(tmp_path, key_path, small_log):
    key = load_private_key(key_path)
    entries = load_entries(small_log)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "small", root)
    path = root / log_id_of(entries) / "000000.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["sig"] = ("0" if envelope["sig"][0] != "0" else "1") \
        + envelope["sig"][1:]
    path.write_text(json.dumps(envelope), encoding="utf-8")
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "failed"
    assert result["failure"]["stage"] == "history"
    assert "signature" in result["failure"]["detail"]


# ------------------------------------------- the real logs + the forgery

def _proof_history(tmp_path, key):
    """Checkpoints over the TRUE proof log, built in-test with a
    test key at the same lengths as the published history."""
    entries = load_entries(TRUE_LOG)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "proof-run-2/kernel", root, length=250)
    _anchor(entries, key, "proof-run-2/kernel", root)
    return entries, root


def test_true_proof_log_verifies(tmp_path, key_path):
    key = load_private_key(key_path)
    entries, root = _proof_history(tmp_path, key)
    assert len(entries) == 507
    assert head_at(entries, 250) == TRUE_HEAD_250
    assert head_at(entries, 507) == TRUE_HEAD_507
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "verified"
    assert result["anchored_length"] == 507
    assert result["unanchored_tail"] == 0


def test_true_proof_log_tail_against_mid_checkpoint_only(
        tmp_path, key_path):
    key = load_private_key(key_path)
    entries = load_entries(TRUE_LOG)
    root = tmp_path / "checkpoints"
    _anchor(entries, key, "proof-run-2/kernel", root, length=250)
    result = verify_entries(entries, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "verified_to_anchor"
    assert result["anchored_length"] == 250
    assert result["unanchored_tail"] == 257


def test_forged_log_passes_internal_chain():
    # Direction one: section 2 alone cannot tell the forgery from
    # the true log. Loading through the kernel's Log class (which
    # raises on a bad chain) must succeed.
    forged = Log(path=FORGED_LOG)
    assert len(forged.entries) == 507
    assert forged.verify_chain() is True
    assert forged.entries[100]["body"]["outcome"] == "deny"
    true = load_entries(TRUE_LOG)
    assert true[100]["body"]["outcome"] == "allow"


def test_forged_log_fails_anchor_at_first_divergent_checkpoint(
        tmp_path, key_path):
    # Direction two: against anchored history, the forgery fails
    # at checkpoint 0 (length 250 — the first checkpoint whose
    # prefix covers the seq-100 rewrite).
    key = load_private_key(key_path)
    _entries, root = _proof_history(tmp_path, key)
    forged = load_entries(FORGED_LOG)
    assert verify_internal_chain(forged) is True
    result = verify_entries(forged, _history(root),
                            public_key_hex(key))
    assert result["outcome"] == "failed"
    assert result["internal_chain_ok"] is True
    failure = result["failure"]
    assert failure["stage"] == "prefix"
    assert failure["checkpoint_seq"] == 0
    assert failure["expected_head"] == TRUE_HEAD_250
    assert failure["actual_head"] == head_at(forged, 250)
    assert failure["actual_head"] != failure["expected_head"]


# ---------------------------------------------------------------- CLI

def _run_cli(*argv, expect=None):
    env = dict(os.environ, JACQUARD_ANCHOR_PASSPHRASE=TEST_PASSPHRASE)
    proc = subprocess.run([sys.executable, JQANCHOR] + list(argv),
                          capture_output=True, text=True, env=env)
    if expect is not None:
        assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
    return proc


def test_cli_end_to_end(tmp_path):
    key = str(tmp_path / "k.ed25519")
    out = _run_cli("keygen", "--key", key, expect=0)
    pub = json.loads(out.stdout)["pubkey"]
    with pytest.raises(AssertionError):
        _run_cli("keygen", "--key", key, expect=0)
    assert _run_cli("keygen", "--key", key).returncode == 2

    log_path = str(tmp_path / "kernel.jsonl")
    log = Log(path=log_path)
    log.append("sense", {"producer": "op", "name": "a", "value": 1})
    log.append("sense", {"producer": "op", "name": "b", "value": 2})
    checkpoints = str(tmp_path / "checkpoints")
    out = _run_cli("anchor", log_path, "--label", "cli-test",
                   "--checkpoints", checkpoints, "--key", key, expect=0)
    body = json.loads(out.stdout)["body"]
    assert body["log_length"] == 2 and body["checkpoint_seq"] == 0

    out = _run_cli("verify", log_path, "--checkpoints", checkpoints,
                   "--pubkey", pub, expect=0)
    assert json.loads(out.stdout)["outcome"] == "verified"

    out = _run_cli("verify", log_path, "--checkpoints",
                   str(tmp_path / "empty"), "--pubkey", pub, expect=3)
    assert json.loads(out.stdout)["outcome"] == "unanchored"
