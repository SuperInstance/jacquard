"""Slice 21: anchor key management (SPEC 15.3 as rewritten in 0.6).

Encrypted at rest with the passphrase supplied at run time,
rotation with continuity over a published key registry, and the
refusals that keep a retired key retired.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import Log  # noqa: E402
from jacquard.anchor import (  # noqa: E402
    AnchorError, anchor_entries, generate_key, key_is_encrypted,
    load_checkpoints, load_entries, load_key_registry,
    load_private_key, public_key_hex, schedule_from_registry,
    verify_entries)

REPO = os.path.join(os.path.dirname(__file__), "..")
JQANCHOR = os.path.join(REPO, "tools", "jqanchor.py")
PASS = "slice21-test-passphrase"
LOG_ID_HOLDER = {}


@pytest.fixture()
def log_path(tmp_path):
    path = str(tmp_path / "kernel.jsonl")
    log = Log(path=path)
    for i in range(6):
        log.append("sense", {"producer": "op", "name": "s%d" % i,
                             "value": i})
    return path


def _key(tmp_path, name, passphrase=PASS):
    path = str(tmp_path / name)
    generate_key(path, passphrase=passphrase)
    return path


def _history(root):
    envelopes, problems = load_checkpoints(str(root))
    assert problems == []
    return envelopes


# ---------------------------------------------------------- encryption

def test_keygen_requires_a_passphrase(tmp_path, monkeypatch):
    monkeypatch.delenv("JACQUARD_ANCHOR_PASSPHRASE", raising=False)
    with pytest.raises(AnchorError):
        generate_key(str(tmp_path / "k.ed25519"))


def test_key_is_encrypted_at_rest(tmp_path):
    path = _key(tmp_path, "k.ed25519")
    assert key_is_encrypted(path)
    with open(path, "rb") as fh:
        assert b"ENCRYPTED" in fh.read()
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_wrong_passphrase_refused(tmp_path):
    path = _key(tmp_path, "k.ed25519")
    with pytest.raises(AnchorError):
        load_private_key(path, passphrase="not-the-passphrase")
    key = load_private_key(path, passphrase=PASS)
    assert public_key_hex(key)


def test_passphrase_via_environment(tmp_path, monkeypatch):
    path = _key(tmp_path, "k.ed25519")
    monkeypatch.setenv("JACQUARD_ANCHOR_PASSPHRASE", PASS)
    assert load_private_key(path) is not None
    monkeypatch.setenv("JACQUARD_ANCHOR_PASSPHRASE", "wrong")
    with pytest.raises(AnchorError):
        load_private_key(path)


def test_legacy_unencrypted_key_still_loads(tmp_path):
    # A pre-0.6 key file (PKCS#8, NoEncryption) must keep loading:
    # migration anchors with it until rotation replaces it.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    path = str(tmp_path / "legacy.ed25519")
    pem = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, pem)
    os.close(fd)
    assert not key_is_encrypted(path)
    assert load_private_key(path) is not None


# ------------------------------------------------------------ rotation

def _rotated_history(tmp_path, log_path):
    """Two checkpoints under key A, then rotation, a third under B.
    Returns (entries, root, pub_a, pub_b, registry)."""
    entries = load_entries(log_path)
    root = tmp_path / "checkpoints"
    key_a = load_private_key(_key(tmp_path, "a.ed25519"), passphrase=PASS)
    anchor_entries(entries, key_a, "rot", str(root), log_length=2)
    anchor_entries(entries, key_a, "rot", str(root), log_length=4)
    registry = {"format": "jacquard/anchor-keys/1", "keys": [
        {"pubkey": public_key_hex(key_a), "status": "retired",
         "signs_from": {}, "signs_until": {}},
        {"pubkey": None, "status": "active",
         "signs_from": {}, "signs_until": {}}]}
    key_b = load_private_key(_key(tmp_path, "b.ed25519"), passphrase=PASS)
    pub_b = public_key_hex(key_b)
    log_id = entries[0]["hash"]
    registry["keys"][0]["signs_until"][log_id] = 1
    registry["keys"][1]["pubkey"] = pub_b
    registry["keys"][1]["signs_from"][log_id] = 2
    schedule = schedule_from_registry(registry, log_id)
    anchor_entries(entries, key_b, "rot", str(root),
                   history_schedule=schedule)
    return entries, root, public_key_hex(key_a), pub_b, registry


def test_rotation_continuity(tmp_path, log_path):
    entries, root, pub_a, pub_b, registry = _rotated_history(
        tmp_path, log_path)
    schedule = schedule_from_registry(registry, entries[0]["hash"])
    result = verify_entries(entries, _history(root), pub_a,
                            schedule=schedule)
    assert result["outcome"] == "verified"
    assert result["checkpoints_checked"] == 3
    # The old key alone no longer verifies the history...
    result = verify_entries(entries, _history(root), pub_a)
    assert result["outcome"] == "failed"
    assert result["failure"]["checkpoint_seq"] == 2
    # ...and neither does the new key alone.
    result = verify_entries(entries, _history(root), pub_b)
    assert result["outcome"] == "failed"
    assert result["failure"]["checkpoint_seq"] == 0


def test_retired_key_cannot_anchor_after_boundary(tmp_path, log_path):
    entries, root, pub_a, _pub_b, registry = _rotated_history(
        tmp_path, log_path)
    schedule = schedule_from_registry(registry, entries[0]["hash"])
    key_a = load_private_key(str(tmp_path / "a.ed25519"), passphrase=PASS)
    with pytest.raises(AnchorError):
        anchor_entries(entries, key_a, "rot", str(root),
                       history_schedule=schedule)


def test_registry_partition_validation(tmp_path, log_path):
    entries = load_entries(log_path)
    log_id = entries[0]["hash"]
    gap = {"format": "jacquard/anchor-keys/1", "keys": [
        {"pubkey": "a" * 64, "status": "retired", "signs_from": {},
         "signs_until": {log_id: 0}},
        {"pubkey": "b" * 64, "status": "active",
         "signs_from": {log_id: 2}, "signs_until": {}}]}
    with pytest.raises(AnchorError):
        schedule_from_registry(gap, log_id)
    overlap = {"format": "jacquard/anchor-keys/1", "keys": [
        {"pubkey": "a" * 64, "status": "retired", "signs_from": {},
         "signs_until": {log_id: 5}},
        {"pubkey": "b" * 64, "status": "active",
         "signs_from": {log_id: 2}, "signs_until": {}}]}
    with pytest.raises(AnchorError):
        schedule_from_registry(overlap, log_id)


def test_cli_rotate_end_to_end(tmp_path):
    env = dict(os.environ, JACQUARD_ANCHOR_PASSPHRASE=PASS)

    def run(*argv, expect=0):
        proc = subprocess.run([sys.executable, JQANCHOR] + list(argv),
                              capture_output=True, text=True, env=env)
        assert proc.returncode == expect, (argv, proc.stdout, proc.stderr)
        return proc

    old_key = str(tmp_path / "old.ed25519")
    pub_a = json.loads(run("keygen", "--key", old_key).stdout)["pubkey"]
    log_file = str(tmp_path / "kernel.jsonl")
    log = Log(path=log_file)
    for i in range(4):
        log.append("sense", {"producer": "op", "name": "s%d" % i,
                             "value": i})
    ck = str(tmp_path / "checkpoints")
    run("anchor", log_file, "--label", "cli-rot", "--checkpoints", ck,
        "--key", old_key, "--length", "2")
    run("anchor", log_file, "--label", "cli-rot", "--checkpoints", ck,
        "--key", old_key)
    new_key = str(tmp_path / "new.ed25519")
    out = json.loads(run("rotate", "--key", old_key, "--new-key", new_key,
                         "--checkpoints", ck).stdout)
    pub_b = out["new_pubkey"]
    assert pub_b != pub_a and key_is_encrypted(new_key)
    registry = load_key_registry(ck)
    log_id = load_entries(log_file)[0]["hash"]
    assert registry["keys"][0]["signs_until"][log_id] == 1
    assert registry["keys"][1]["signs_from"][log_id] == 2
    # Extend the log and anchor with the successor under the registry.
    log.append("sense", {"producer": "op", "name": "s4", "value": 4})
    run("anchor", log_file, "--label", "cli-rot", "--checkpoints", ck,
        "--key", new_key, "--history-keys", ck)
    out = json.loads(run("verify", log_file, "--checkpoints", ck,
                         "--keys", ck).stdout)
    assert out["outcome"] == "verified"
    assert out["checkpoints_checked"] == 3
    proc = run("verify", log_file, "--checkpoints", ck,
               "--pubkey", pub_a, expect=1)
    assert json.loads(proc.stdout)["outcome"] == "failed"
