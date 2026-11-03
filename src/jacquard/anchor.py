"""Chain-head anchoring (SPEC section 15).

Signed checkpoints of a log prefix — (log length, head hash, spec
version) — published outside the kernel's store, so a third party
can verify a presented log against history the operator cannot
silently rewrite. The kernel never anchors and imports no signing
code: this module is anchor *tooling*, it is not exported from
`jacquard/__init__`, and it is the only part of the package that
depends on the `cryptography` package (Ed25519). Importing
`jacquard` itself never requires that package.

Vocabulary, per the spec: a checkpoint *body* is the signed
object (exactly eight keys); a checkpoint *document* / envelope
is `{"body", "pubkey", "sig"}`; the *checkpoint hash* is the
section-1 hash of the body; checkpoints for one log form their
own hash-chained sequence via `prev_checkpoint`.

Verification reports exactly one outcome — `verified`,
`verified_to_anchor` (anchored prefix and unanchored tail as
distinct numbers), `unanchored`, or `failed` (naming the first
divergent checkpoint, or the history / internal failure) — never
a bare boolean.
"""
import json
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)

from .canonical import SPEC_VERSION, canonical, hash_of
from .log import GENESIS_PREV

ANCHOR_FORMAT = "jacquard/anchor/1"
BODY_KEYS = frozenset({
    "format", "log_id", "label", "checkpoint_seq", "log_length",
    "head_hash", "spec", "prev_checkpoint"})
ENVELOPE_KEYS = frozenset({"body", "pubkey", "sig"})
DEFAULT_KEY_PATH = os.path.join(
    os.path.expanduser("~"), ".jacquard", "anchor-key.ed25519")
HEX = frozenset("0123456789abcdef")


class AnchorError(Exception):
    """A refusal of the anchor tooling, with a human detail."""


def _is_hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(c in HEX for c in value))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------- keys

def _inside_work_tree(path):
    """True if any ancestor of `path` contains a `.git` entry."""
    current = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def generate_key(path=DEFAULT_KEY_PATH):
    """Generate the operator keypair once (SPEC 15.3).

    Refuses to overwrite an existing key and refuses a path
    inside a version-controlled tree. Writes the private key PEM
    (PKCS#8, unencrypted) with mode 0600 and returns the public
    key hex. The private key is never printed or returned.
    """
    if os.path.exists(path):
        raise AnchorError("key already exists, refusing to "
                          "overwrite: %s" % path)
    if _inside_work_tree(os.path.dirname(path) or "."):
        raise AnchorError("key path is inside a version-controlled "
                          "tree, refusing: %s" % path)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, pem)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    return public_key_hex(key)


def load_private_key(path=DEFAULT_KEY_PATH):
    if not os.path.exists(path):
        raise AnchorError("no anchor key at %s (run keygen first)"
                          % path)
    mode = os.stat(path).st_mode & 0o777
    if mode & 0o077:
        raise AnchorError(
            "anchor key at %s has mode %o; it must not be readable "
            "by group or others (chmod 600)" % (path, mode))
    with open(path, "rb") as fh:
        pem = fh.read()
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except Exception as exc:
        raise AnchorError("cannot load anchor key at %s: %s"
                          % (path, exc))
    if not isinstance(key, Ed25519PrivateKey):
        raise AnchorError("anchor key at %s is not Ed25519" % path)
    return key


def public_key_hex(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw).hex()


def _verify_signature(pubkey_hex, body, sig_hex):
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
    try:
        pub.verify(bytes.fromhex(sig_hex), canonical(body))
    except InvalidSignature:
        return False
    return True


# ---------------------------------------------------------------- logs

def load_entries(path):
    """Load a JSONL log's entries WITHOUT chain enforcement, so
    verification can report an internal-chain failure distinctly
    from an anchor failure (the Log class raises instead)."""
    entries = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def verify_internal_chain(entries):
    """The section-2 chain check, as a boolean (Log.verify_chain
    over raw entries)."""
    prev = GENESIS_PREV
    for i, entry in enumerate(entries):
        if entry.get("seq") != i or entry.get("prev") != prev:
            return False
        body = {k: entry.get(k)
                for k in ("seq", "prev", "kind", "body", "spec")}
        if hash_of(body) != entry.get("hash"):
            return False
        prev = entry["hash"]
    return True


def log_id_of(entries):
    """SPEC 15.2: the genesis entry's hash; all zeros if empty."""
    return entries[0]["hash"] if entries else GENESIS_PREV


def head_at(entries, length):
    if length == 0:
        return GENESIS_PREV
    return entries[length - 1]["hash"]


# ---------------------------------------------------------- checkpoints

def checkpoint_hash(body):
    return hash_of(body)


def build_body(entries, label, checkpoint_seq, prev_checkpoint,
               log_length=None):
    if log_length is None:
        log_length = len(entries)
    if not _is_int(log_length) or not 0 <= log_length <= len(entries):
        raise AnchorError("log_length %r outside 0..%d"
                          % (log_length, len(entries)))
    return {"format": ANCHOR_FORMAT,
            "log_id": log_id_of(entries),
            "label": label,
            "checkpoint_seq": checkpoint_seq,
            "log_length": log_length,
            "head_hash": head_at(entries, log_length),
            "spec": SPEC_VERSION,
            "prev_checkpoint": prev_checkpoint}


def sign_body(body, key):
    return {"body": body,
            "pubkey": public_key_hex(key),
            "sig": key.sign(canonical(body)).hex()}


def envelope_bytes(envelope):
    """The file form (SPEC 15.1): canonical bytes + newline."""
    return canonical(envelope) + b"\n"


def checkpoint_relpath(body):
    """The reference git layout (SPEC 15.4)."""
    return os.path.join(body["log_id"], "%06d.json"
                        % body["checkpoint_seq"])


def validate_body(body):
    """Return a detail string, or None if `body` is a well-formed
    checkpoint body (SPEC 15.1: exactly the eight keys)."""
    if not isinstance(body, dict):
        return "body is not an object"
    if frozenset(body) != BODY_KEYS:
        return ("body keys are %s, expected exactly %s"
                % (sorted(body), sorted(BODY_KEYS)))
    if body["format"] != ANCHOR_FORMAT:
        return "format is %r" % (body["format"],)
    if not _is_hex(body["log_id"], 64):
        return "log_id is not hex64"
    if not isinstance(body["label"], str):
        return "label is not a string"
    if not _is_int(body["checkpoint_seq"]) or body["checkpoint_seq"] < 0:
        return "checkpoint_seq is not an integer >= 0"
    if not _is_int(body["log_length"]) or body["log_length"] < 0:
        return "log_length is not an integer >= 0"
    if not _is_hex(body["head_hash"], 64):
        return "head_hash is not hex64"
    if body["spec"] != SPEC_VERSION:
        return "spec is %r, expected %r" % (body["spec"], SPEC_VERSION)
    prev = body["prev_checkpoint"]
    if body["checkpoint_seq"] == 0 and prev is not None:
        return "checkpoint_seq 0 must carry prev_checkpoint null"
    if body["checkpoint_seq"] > 0 and not _is_hex(prev, 64):
        return "prev_checkpoint is not hex64"
    return None


def load_checkpoints(root):
    """Every checkpoint envelope under `root`: a directory searched
    recursively for `*.json` files, a `checkpoints/` subdirectory
    of it if one exists, or a single checkpoint file. Unparseable
    files are reported, not silently skipped."""
    if os.path.isfile(root):
        candidates = [root]
    else:
        search = os.path.join(root, "checkpoints")
        if not os.path.isdir(search):
            search = root
        candidates = []
        for dirpath, _dirs, files in os.walk(search):
            for name in sorted(files):
                if name.endswith(".json"):
                    candidates.append(os.path.join(dirpath, name))
    envelopes, problems = [], []
    for path in sorted(candidates):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                envelope = json.load(fh)
        except Exception as exc:
            problems.append("%s: %s" % (path, exc))
            continue
        if not isinstance(envelope, dict) \
                or frozenset(envelope) != ENVELOPE_KEYS:
            problems.append("%s: not a checkpoint envelope" % path)
            continue
        envelopes.append(envelope)
    return envelopes, problems


def history_for(envelopes, log_id):
    selected = [e for e in envelopes
                if isinstance(e.get("body"), dict)
                and e["body"].get("log_id") == log_id]
    return sorted(selected, key=lambda e: e["body"]["checkpoint_seq"])


def _scheduled_key(schedule, checkpoint_seq):
    """schedule: sorted [(from_seq, pubkey_hex), ...]."""
    chosen = None
    for from_seq, pubkey_hex in schedule:
        if checkpoint_seq >= from_seq:
            chosen = pubkey_hex
    return chosen


def authenticate_history(history, schedule):
    """SPEC 15.5 step 1 over one log's selected history.
    Returns (ok, failure_detail, offending_checkpoint_seq)."""
    prev_hash = None
    for expected_seq, envelope in enumerate(history):
        body = envelope["body"]
        detail = validate_body(body)
        if detail is not None:
            return False, "checkpoint %d: %s" % (expected_seq, detail), \
                body.get("checkpoint_seq")
        if body["checkpoint_seq"] != expected_seq:
            return False, ("checkpoint sequence gap: expected seq %d, "
                           "found %d" % (expected_seq,
                                         body["checkpoint_seq"])), \
                body["checkpoint_seq"]
        if body["prev_checkpoint"] != prev_hash:
            return False, ("checkpoint %d: prev_checkpoint does not "
                           "recompute" % expected_seq), expected_seq
        pinned = _scheduled_key(schedule, expected_seq)
        if pinned is None or envelope["pubkey"] != pinned:
            return False, ("checkpoint %d: envelope pubkey is not the "
                           "pinned key for its sequence"
                           % expected_seq), expected_seq
        if not _is_hex(envelope["sig"], 128) \
                or not _verify_signature(pinned, body, envelope["sig"]):
            return False, ("checkpoint %d: signature does not verify"
                           % expected_seq), expected_seq
        prev_hash = checkpoint_hash(body)
    return True, None, None


# ------------------------------------------------------------- verify

def verify_entries(entries, envelopes, pubkey_hex, schedule=None):
    """The SPEC 15.5 procedure over raw entries + envelopes.

    `pubkey_hex` is the pinned key; `schedule` optionally encodes
    one or more rotations as [(from_seq, pubkey_hex), ...] and
    defaults to [(0, pubkey_hex)].
    """
    if schedule is None:
        schedule = [(0, pubkey_hex)]
    log_id = log_id_of(entries)
    result = {"outcome": None,
              "log_id": log_id,
              "log_length": len(entries),
              "anchored_length": 0,
              "unanchored_tail": len(entries),
              "checkpoints_checked": 0,
              "internal_chain_ok": verify_internal_chain(entries),
              "failure": None}
    history = history_for(envelopes, log_id)
    if not history:
        result["outcome"] = "unanchored"
        return result
    ok, detail, offender = authenticate_history(history, schedule)
    if not ok:
        result["outcome"] = "failed"
        result["failure"] = {"stage": "history",
                             "checkpoint_seq": offender,
                             "detail": detail}
        return result
    if not result["internal_chain_ok"]:
        result["outcome"] = "failed"
        result["failure"] = {"stage": "internal",
                             "checkpoint_seq": None,
                             "detail": "presented log fails its own "
                                       "hash-chain verification"}
        return result
    for envelope in history:
        body = envelope["body"]
        result["checkpoints_checked"] += 1
        if body["log_length"] > len(entries):
            result["outcome"] = "failed"
            result["failure"] = {
                "stage": "prefix",
                "checkpoint_seq": body["checkpoint_seq"],
                "detail": "checkpoint anchors length %d, presented "
                          "log has %d entries (truncated or missing "
                          "anchored history)"
                          % (body["log_length"], len(entries)),
                "expected_head": body["head_hash"],
                "actual_head": None}
            return result
        actual = head_at(entries, body["log_length"])
        if actual != body["head_hash"]:
            result["outcome"] = "failed"
            result["failure"] = {
                "stage": "prefix",
                "checkpoint_seq": body["checkpoint_seq"],
                "detail": "first divergent checkpoint: checkpoint "
                          "%d anchors length %d at head %s, presented "
                          "log's head at that length is %s"
                          % (body["checkpoint_seq"], body["log_length"],
                             body["head_hash"], actual),
                "expected_head": body["head_hash"],
                "actual_head": actual}
            return result
        result["anchored_length"] = body["log_length"]
    result["unanchored_tail"] = len(entries) - result["anchored_length"]
    result["outcome"] = ("verified" if result["unanchored_tail"] == 0
                         else "verified_to_anchor")
    return result


# ------------------------------------------------------------- anchor

def anchor_entries(entries, key, label, checkpoints_root,
                   log_length=None):
    """Build, sign and store the next checkpoint for `entries`.

    Refuses a log whose internal chain fails, a checkpoint file
    that already exists, and a `log_length` behind the last
    anchored length (anchoring backwards is a tool-level refusal;
    the spec's sequence is append-only). Existing history for the
    log is authenticated under the key's own public key first —
    a publisher does not extend a history it cannot verify.
    Returns (envelope, path).
    """
    if not verify_internal_chain(entries):
        raise AnchorError("refusing to anchor a log whose internal "
                          "chain fails verification")
    envelopes, problems = load_checkpoints(checkpoints_root)
    if problems:
        raise AnchorError("existing checkpoint store has problems: %s"
                          % "; ".join(problems))
    history = history_for(envelopes, log_id_of(entries))
    if history:
        ok, detail, _seq = authenticate_history(
            history, [(0, public_key_hex(key))])
        if not ok:
            raise AnchorError("existing history does not authenticate "
                              "under this key: %s" % detail)
        last = history[-1]["body"]
        if log_length is not None and log_length < last["log_length"]:
            raise AnchorError(
                "log_length %d is behind the last anchored length %d"
                % (log_length, last["log_length"]))
        seq = last["checkpoint_seq"] + 1
        prev = checkpoint_hash(last)
    else:
        seq, prev = 0, None
    body = build_body(entries, label, seq, prev, log_length)
    envelope = sign_body(body, key)
    path = os.path.join(checkpoints_root, checkpoint_relpath(body))
    if os.path.exists(path):
        raise AnchorError("checkpoint file already exists: %s" % path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(envelope_bytes(envelope))
    return envelope, path
