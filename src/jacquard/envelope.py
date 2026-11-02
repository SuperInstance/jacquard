"""Envelopes (SPEC section 3)."""
from .canonical import SPEC_SEAL, hash_of

ENVELOPE_FIELDS = ("v", "id", "producer", "kind", "body",
                   "declared_effects", "spec_seal")


def make_envelope(producer, kind, body, declared_effects, idem_id):
    return {"v": 1, "id": idem_id, "producer": producer, "kind": kind,
            "body": body, "declared_effects": sorted(set(declared_effects)),
            "spec_seal": SPEC_SEAL}


def envelope_hash(envelope):
    return hash_of(envelope)


def validate_envelope(envelope):
    """Return a refusal (name, detail) or None if well-formed."""
    if not isinstance(envelope, dict):
        return ("FIELD", "envelope is not an object")
    for field in ENVELOPE_FIELDS:
        if field not in envelope:
            return ("FIELD", "envelope missing field: %s" % field)
    if envelope["v"] != 1:
        return ("SPEC", "unsupported envelope version: %r" % (envelope["v"],))
    if envelope["spec_seal"] != SPEC_SEAL:
        return ("SPEC", "spec seal mismatch")
    if envelope["kind"] not in ("proposal", "definition", "machine"):
        return ("FIELD", "unknown envelope kind: %r" % (envelope["kind"],))
    if not isinstance(envelope["declared_effects"], list):
        return ("FIELD", "declared_effects must be a list")
    return None
