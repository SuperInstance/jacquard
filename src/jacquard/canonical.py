"""Canonical serialisation and hashing (SPEC section 1).

One canonical JSON form for everything hashed or stored: UTF-8,
sorted keys, no whitespace, and no floating-point numbers anywhere.
Quantities are integers in stated units.
"""
import hashlib
import json

SPEC_VERSION = "jacquard/0.5"
SPEC_SEAL = hashlib.sha256(b"jacquard-spec/0.5").hexdigest()


def _check(value, path="$"):
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise TypeError("float at %s: canonical form is integers only" % path)
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _check(item, "%s[%d]" % (path, i))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("non-string key at %s" % path)
            _check(item, "%s.%s" % (path, key))
        return
    raise TypeError("uncanonical type at %s: %r" % (path, type(value)))


def canonical(obj):
    """Canonical bytes for a structure (SPEC section 1)."""
    _check(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def hash_of(obj):
    """Lowercase hex SHA-256 of the canonical bytes."""
    return hashlib.sha256(canonical(obj)).hexdigest()
