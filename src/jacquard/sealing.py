"""Sealed exports (SPEC section 16).

Redaction as a view: designated fields of a log's entries are
sealed — committed in the log itself by `seal` entries — and an
export replaces those values with hash (or keyed-HMAC)
commitments, such that the export still verifies against the
log's anchors. The anchored log is never altered. Like
`jacquard.anchor`, this module is export *tooling*: it is not
exported from `jacquard/__init__`, and the kernel never seals.

Verification reports the section 15.5 vocabulary — `verified`,
`verified_to_anchor`, `unanchored`, `failed` (naming the stage
and the first divergent checkpoint or entry) — plus
`seals_applied`, `seals_anchored` and `commitments_checked`,
never a bare boolean.
"""
import copy
import hashlib
import hmac
import json

from .anchor import (authenticate_history, head_at, history_for,
                     load_checkpoints)
from .canonical import canonical, hash_of
from .log import GENESIS_PREV

EXPORT_FORMAT = "jacquard/redacted-export/1"
SEAL_DOMAIN = "jacquard/seal/1"
SEAL_KEYS = frozenset({"entry_seq", "field", "class", "mode",
                       "commitment"})
EXPORT_KEYS = frozenset({"format", "log_id", "source_length",
                         "exported_length", "seal_set_hash", "entries"})
HEX = frozenset("0123456789abcdef")


class SealError(Exception):
    """A refusal of the sealing tooling, with a human detail."""


def _is_hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(c in HEX for c in value))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ------------------------------------------------------------ field paths

def resolve_field(body, field):
    """The value at a dotted path inside an entry body (SPEC
    16.1), or SealError if the path does not resolve."""
    node = body
    for part in field.split("."):
        if isinstance(node, dict):
            if part not in node:
                raise SealError("field %r does not resolve: no key %r"
                                % (field, part))
            node = node[part]
        elif isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                raise SealError("field %r does not resolve at %r"
                                % (field, part))
            node = node[int(part)]
        else:
            raise SealError("field %r does not resolve at %r"
                            % (field, part))
    return node


def _set_field(body, field, replacement):
    parts = field.split(".")
    node = body
    for part in parts[:-1]:
        node = node[part] if isinstance(node, dict) else node[int(part)]
    last = parts[-1]
    if isinstance(node, dict):
        node[last] = replacement
    else:
        node[int(last)] = replacement


def _find_markers(node, prefix=""):
    """All (field, marker) positions in an entry body whose value
    is a seal marker (SPEC 16.2)."""
    found = []
    if isinstance(node, dict):
        if frozenset(node) == frozenset({"sealed", "class"}) \
                and _is_hex(node.get("sealed"), 64) \
                and isinstance(node.get("class"), str):
            found.append((prefix, node))
            return found
        for key in sorted(node):
            found.extend(_find_markers(
                node[key], key if not prefix else prefix + "." + key))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_find_markers(
                item, str(i) if not prefix else prefix + "." + str(i)))
    return found


# -------------------------------------------------------------- commitments

def commitment_for(entry_seq, field, value, mode, redaction_key=None):
    """The seal commitment (SPEC 16.1): hash of the domain-bound
    preimage, or its HMAC-SHA-256 under the redaction key."""
    preimage = {"domain": SEAL_DOMAIN, "entry_seq": entry_seq,
                "field": field, "value": value}
    if mode == "hash":
        return hash_of(preimage)
    if mode == "keyed":
        if redaction_key is None:
            raise SealError("keyed mode requires a redaction key")
        return hmac.new(redaction_key, canonical(preimage),
                        hashlib.sha256).hexdigest()
    raise SealError("unknown seal mode %r" % (mode,))


def build_seals(entries, targets, mode="hash", redaction_key=None):
    """Seal dicts for (entry_seq, field, class) targets, computed
    over the values the named entries actually hold. Refuses a
    target at or beyond the log's end, a `seal` entry, and a path
    that does not resolve."""
    seals = []
    for entry_seq, field, cls in targets:
        if not _is_int(entry_seq) or not 0 <= entry_seq < len(entries):
            raise SealError("seal target entry_seq %r outside the log"
                            % (entry_seq,))
        entry = entries[entry_seq]
        if entry.get("kind") == "seal":
            raise SealError("seals do not seal seals (entry %d)"
                            % entry_seq)
        value = resolve_field(entry["body"], field)
        seals.append({"entry_seq": entry_seq, "field": field,
                      "class": cls, "mode": mode,
                      "commitment": commitment_for(
                          entry_seq, field, value, mode, redaction_key)})
    return seals


def targets_for_field(entries, field, cls):
    """Every (entry_seq, field, class) target at which `field`
    resolves in an entry body — the CLI's sealing convenience."""
    targets = []
    for entry in entries:
        if entry.get("kind") == "seal":
            continue
        try:
            resolve_field(entry["body"], field)
        except SealError:
            continue
        targets.append((entry["seq"], field, cls))
    return targets


def collect_seals(entries):
    """Every seal committed in `entries`, annotated with the
    `seal_entry_seq` of the entry that carries it."""
    out = []
    for entry in entries:
        if entry.get("kind") != "seal":
            continue
        for seal in entry["body"].get("seals", []):
            out.append(dict(seal, seal_entry_seq=entry["seq"]))
    return out


def _applied_seals(entries, exported_length):
    return [s for s in collect_seals(entries[:exported_length])
            if s["entry_seq"] < exported_length]


def _seal_set(applied):
    trimmed = [{"entry_seq": s["entry_seq"], "field": s["field"],
                "class": s["class"], "mode": s["mode"],
                "commitment": s["commitment"]} for s in applied]
    return sorted(trimmed, key=lambda s: (s["entry_seq"], s["field"]))


def seal_set_hash(applied):
    return hash_of(_seal_set(applied))


# ------------------------------------------------------------------ export

def make_export(entries, exported_length=None):
    """The redacted export document (SPEC 16.2) for a prefix of
    `entries`. Pure: the source entries are never mutated."""
    if exported_length is None:
        exported_length = len(entries)
    if not 0 <= exported_length <= len(entries):
        raise SealError("exported_length %r outside 0..%d"
                        % (exported_length, len(entries)))
    applied = _applied_seals(entries, exported_length)
    carried = copy.deepcopy(entries[:exported_length])
    by_target = {(s["entry_seq"], s["field"]): s for s in applied}
    if len(by_target) != len(applied):
        raise SealError("duplicate seals for one (entry, field)")
    for (entry_seq, field), seal in by_target.items():
        _set_field(carried[entry_seq]["body"], field,
                   {"sealed": seal["commitment"], "class": seal["class"]})
    return {"format": EXPORT_FORMAT,
            "log_id": entries[0]["hash"] if entries else GENESIS_PREV,
            "source_length": len(entries),
            "exported_length": exported_length,
            "seal_set_hash": seal_set_hash(applied),
            "entries": carried}


def export_bytes(export):
    return canonical(export) + b"\n"


# ------------------------------------------------------------------ verify

def _fail(result, stage, detail, **extra):
    result["outcome"] = "failed"
    result["failure"] = dict({"stage": stage, "detail": detail}, **extra)
    return result


def verify_export(export, envelopes, pubkey_hex, schedule=None,
                  original_entries=None, redaction_key=None):
    """The SPEC 16.3 procedure. `envelopes` is a checkpoint
    history as in section 15.5; `original_entries`, when given,
    lets commitments be checked against true values."""
    if schedule is None:
        schedule = [(0, pubkey_hex)]
    entries = export.get("entries") if isinstance(export, dict) else None
    result = {"outcome": None,
              "log_id": export.get("log_id") if isinstance(export, dict)
              else None,
              "source_length": export.get("source_length")
              if isinstance(export, dict) else None,
              "exported_length": len(entries) if entries else 0,
              "anchored_length": 0, "unanchored_tail": 0,
              "checkpoints_checked": 0, "checkpoints_beyond": 0,
              "seals_applied": 0, "seals_anchored": True,
              "commitments_checked": "consistency", "failure": None}
    # 1. header
    if not isinstance(export, dict) or frozenset(export) != EXPORT_KEYS \
            or export.get("format") != EXPORT_FORMAT \
            or not isinstance(entries, list):
        return _fail(result, "header", "not a %s document" % EXPORT_FORMAT)
    exported_length = export["exported_length"]
    if exported_length != len(entries) \
            or not _is_int(export["source_length"]) \
            or exported_length > export["source_length"]:
        return _fail(result, "header",
                     "exported_length does not match the carried entries "
                     "or exceeds source_length")
    genesis = entries[0]["hash"] if entries else GENESIS_PREV
    if export["log_id"] != genesis:
        return _fail(result, "header",
                     "log_id does not equal the genesis entry's hash")
    applied = _applied_seals(entries, exported_length)
    result["seals_applied"] = len(applied)
    if seal_set_hash(applied) != export["seal_set_hash"]:
        return _fail(result, "header",
                     "seal_set_hash does not recompute from the carried "
                     "seal entries")
    # 2. linkage
    prev = GENESIS_PREV
    for i, entry in enumerate(entries):
        if entry.get("seq") != i or entry.get("prev") != prev:
            return _fail(result, "linkage",
                         "entry %d breaks the seq/prev chain" % i,
                         entry_seq=i)
        prev = entry["hash"]
    # 3 + 4. recompute / marker consistency
    by_target = {}
    for seal in applied:
        key = (seal["entry_seq"], seal["field"])
        if key in by_target:
            return _fail(result, "seals",
                         "duplicate seals for entry %d field %r" % key,
                         entry_seq=key[0])
        by_target[key] = seal
    used = set()
    for entry in entries:
        markers = _find_markers(entry["body"])
        if entry.get("kind") == "seal" and markers:
            return _fail(result, "seals",
                         "seal entry %d carries a marker" % entry["seq"],
                         entry_seq=entry["seq"])
        if not markers:
            body = {k: entry.get(k)
                    for k in ("seq", "prev", "kind", "body", "spec")}
            if hash_of(body) != entry.get("hash"):
                return _fail(result, "entries",
                             "entry %d does not recompute to its retained "
                             "hash" % entry["seq"], entry_seq=entry["seq"])
            continue
        for field, marker in markers:
            seal = by_target.get((entry["seq"], field))
            if seal is None:
                return _fail(result, "seals",
                             "entry %d field %r carries a marker with no "
                             "committed seal" % (entry["seq"], field),
                             entry_seq=entry["seq"])
            if marker["sealed"] != seal["commitment"] \
                    or marker["class"] != seal["class"]:
                return _fail(result, "seals",
                             "entry %d field %r marker does not match its "
                             "committed seal" % (entry["seq"], field),
                             entry_seq=entry["seq"])
            used.add((entry["seq"], field))
    if used != frozenset(by_target):
        missing = sorted(frozenset(by_target) - used)
        return _fail(result, "seals",
                     "applied seals not used by any marker: %s"
                     % (missing,), entry_seq=missing[0][0])
    # 5. anchor comparison over retained hashes
    history = history_for(envelopes, export["log_id"])
    if not history:
        result["outcome"] = "unanchored"
        result["unanchored_tail"] = exported_length
        return result
    ok, detail, offender = authenticate_history(history, schedule)
    if not ok:
        return _fail(result, "history", detail, checkpoint_seq=offender)
    for envelope in history:
        body = envelope["body"]
        if body["log_length"] > exported_length:
            result["checkpoints_beyond"] += 1
            continue
        result["checkpoints_checked"] += 1
        actual = head_at(entries, body["log_length"])
        if actual != body["head_hash"]:
            result["unanchored_tail"] = exported_length \
                - result["anchored_length"]
            return _fail(result, "prefix",
                         "first divergent checkpoint: checkpoint %d "
                         "anchors length %d at head %s, export's retained "
                         "head at that length is %s"
                         % (body["checkpoint_seq"], body["log_length"],
                            body["head_hash"], actual),
                         checkpoint_seq=body["checkpoint_seq"],
                         expected_head=body["head_hash"],
                         actual_head=actual)
        result["anchored_length"] = body["log_length"]
    result["unanchored_tail"] = exported_length - result["anchored_length"]
    result["seals_anchored"] = all(
        s["seal_entry_seq"] < result["anchored_length"] for s in applied)
    # 6. commitment checking against the original, when supplied
    if original_entries is not None:
        checked_all = True
        for seal in applied:
            if seal["mode"] == "keyed" and redaction_key is None:
                checked_all = False
                continue
            true_value = resolve_field(
                original_entries[seal["entry_seq"]]["body"], seal["field"])
            expected = commitment_for(seal["entry_seq"], seal["field"],
                                      true_value, seal["mode"],
                                      redaction_key)
            if expected != seal["commitment"]:
                return _fail(result, "commitment",
                             "seal for entry %d field %r does not commit "
                             "to the original value"
                             % (seal["entry_seq"], seal["field"]),
                             entry_seq=seal["entry_seq"])
        if checked_all:
            result["commitments_checked"] = (
                "keyed" if any(s["mode"] == "keyed" for s in applied)
                else "full")
    result["outcome"] = ("verified" if result["unanchored_tail"] == 0
                         else "verified_to_anchor")
    return result


def load_export(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
