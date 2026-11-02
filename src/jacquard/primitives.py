"""The 26 primitives (SPEC section 6) and the evaluation context.

Tier P primitives are pure: they read state views and return
values. Tier E verbs are effects: they appear in definitions and
proposal request lists and are executed only by the kernel, never
by evaluation, so they have signatures here but no implementation.

The evaluator's syntax forms (dup, drop, swap, over, snoc, assoc,
getf, first, cat) manipulate only values on the evaluation stack.
They are not primitives: they grant no access to state or effects.
"""
from .canonical import hash_of
from .state import Refusal

# name -> (ins, outs). P11-P15 are operator families inside their
# numbered slots: the count of primitives is the count of slots.
TIER_P = {
    "self": ([], ["str"]),                       # P1
    "now": ([], ["int"]),                        # P2
    "get": (["str"], ["val"]),                   # P3
    "keys": (["str"], ["list"]),                 # P4
    "cands": (["str"], ["list"]),                # P5
    "age": (["int"], ["int"]),                   # P6
    "record": (["str", "str"], ["map"]),         # P7
    "sense": (["str"], ["val"]),                 # P8
    "similar": (["str", "int"], ["list"]),       # P9
    "history": (["str", "int"], ["list"]),       # P10
    "eq": (["val", "val"], ["bool"]),            # P11 comparisons
    "lt": (["val", "val"], ["bool"]),
    "gt": (["val", "val"], ["bool"]),
    "and": (["bool", "bool"], ["bool"]),         # P12 boolean core
    "or": (["bool", "bool"], ["bool"]),
    "not": (["bool"], ["bool"]),
    "add": (["int", "int"], ["int"]),            # P13 arithmetic
    "sub": (["int", "int"], ["int"]),
    "mul": (["int", "int"], ["int"]),
    "div": (["int", "int"], ["int"]),
    "mod": (["int", "int"], ["int"]),
    "neg": (["int"], ["int"]),                   # P14 unary / pair
    "abs": (["int"], ["int"]),
    "min2": (["int", "int"], ["int"]),
    "max2": (["int", "int"], ["int"]),
    "count": (["list"], ["int"]),                # P15 aggregations
    "sum": (["list"], ["int"]),
    "min": (["list"], ["val"]),
    "max": (["list"], ["val"]),
    "contains": (["list", "val"], ["bool"]),
    "hash": (["val"], ["str"]),                  # P16 seals
    "verify": (["val", "str"], ["bool"]),
    "evidence": (["int"], ["list"]),             # P17
    "def": (["str"], ["map"]),                   # P18 introspection
}

TIER_E = {
    "write": (["str", "val"], []),               # E1
    "dispatch": (["map"], []),                   # E2
    "spend": (["str", "int"], []),               # E3
    "notify": (["str", "val"], []),              # E4
    "send": (["str", "val"], []),                # E5
    "schedule": (["int", "map"], []),            # E6
    "define": (["map"], []),                     # E7
    "checkpoint": (["str"], []),                 # E8
}

PRIMITIVES = {}
for _name, (_ins, _outs) in TIER_P.items():
    PRIMITIVES[_name] = {"tier": "P", "ins": _ins, "outs": _outs}
for _name, (_ins, _outs) in TIER_E.items():
    PRIMITIVES[_name] = {"tier": "E", "ins": _ins, "outs": _outs}

SYNTAX_FORMS = {"dup", "drop", "swap", "over", "snoc", "assoc",
                "getf", "first", "cat"}

EFFECT_VERBS = sorted(TIER_E.keys())


def _int(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        raise Refusal("FIELD", "%s expects an integer, got %r" % (what, value))
    return value


class EvalContext:
    """Read-only views a word may use during evaluation."""

    def __init__(self, state, entries, producer, tentative=None,
                 record_lookup=None):
        self.state = state
        self.entries = entries
        self.producer = producer
        self.tentative = tentative if tentative is not None else {}
        self.record_lookup = record_lookup

    @property
    def now_seq(self):
        return len(self.entries)


def shape_key(cls, effects):
    """The canonical key of a proposal shape: class and sorted
    effect verbs. The learner mines shapes under this key."""
    return "%s|%s" % (cls, ",".join(sorted(effects)))


def _similar(ctx, shape, k):
    """Up to k decisions in the actor's own history whose shape
    key matches `shape` ("<class>|<verb,verb,...>"), oldest
    first. Each is {"class", "effects", "outcome"}."""
    matches = []
    for entry in ctx.entries:
        if entry["kind"] != "decision":
            continue
        body = entry["body"]
        if body.get("producer") != ctx.producer:
            continue
        if shape_key(body.get("class", "work"),
                     body.get("effects", [])) != shape:
            continue
        matches.append({"class": body.get("class", "work"),
                        "effects": body.get("effects", []),
                        "outcome": body.get("outcome")})
    k = _int(k, "similar")
    return matches[-k:] if k > 0 else []


def _history(ctx, unit, window):
    values = []
    for entry in ctx.entries:
        if entry["kind"] == "execution":
            for applied in entry["body"].get("applied", []):
                if applied.get("verb") == "write" and applied["args"][0] == unit:
                    values.append(applied["args"][1])
    if window is not None and window >= 0:
        values = values[-window:] if window else []
    return values


IMPLS = {
    "self": lambda ctx: ctx.producer,
    "now": lambda ctx: ctx.now_seq,
    "get": lambda ctx, unit: ctx.state.units.get(unit),
    "keys": lambda ctx, prefix: sorted(
        k for k in ctx.state.units if k.startswith(prefix)),
    "cands": lambda ctx, unit: list(ctx.tentative.get(unit, [])),
    "age": lambda ctx, seq: max(0, ctx.now_seq - _int(seq, "age")),
    "record": lambda ctx, producer, cls: (
        ctx.record_lookup(producer, cls) if ctx.record_lookup else {}),
    "sense": lambda ctx, name: ctx.state.senses.get(name),
    # P9: the similarity index over the log, populated since the
    # learner landed (Phase 2, slice 6): decisions in the actor's
    # own history whose shape key matches, most recent last.
    "similar": lambda ctx, shape, k: _similar(ctx, shape, k),
    "history": lambda ctx, unit, window: _history(
        ctx, unit, _int(window, "history")),
    "eq": lambda ctx, a, b: a == b,
    "lt": lambda ctx, a, b: a < b,
    "gt": lambda ctx, a, b: a > b,
    "and": lambda ctx, a, b: bool(a) and bool(b),
    "or": lambda ctx, a, b: bool(a) or bool(b),
    "not": lambda ctx, a: not a,
    "add": lambda ctx, a, b: _int(a, "add") + _int(b, "add"),
    "sub": lambda ctx, a, b: _int(a, "sub") - _int(b, "sub"),
    "mul": lambda ctx, a, b: _int(a, "mul") * _int(b, "mul"),
    "div": lambda ctx, a, b: _divmod(ctx, a, b)[0],
    "mod": lambda ctx, a, b: _divmod(ctx, a, b)[1],
    "neg": lambda ctx, a: -_int(a, "neg"),
    "abs": lambda ctx, a: abs(_int(a, "abs")),
    "min2": lambda ctx, a, b: min(_int(a, "min2"), _int(b, "min2")),
    "max2": lambda ctx, a, b: max(_int(a, "max2"), _int(b, "max2")),
    "count": lambda ctx, xs: len(xs),
    "sum": lambda ctx, xs: sum(_int(x, "sum") for x in xs),
    "min": lambda ctx, xs: min(xs) if xs else None,
    "max": lambda ctx, xs: max(xs) if xs else None,
    "contains": lambda ctx, xs, x: x in xs,
    "hash": lambda ctx, value: hash_of(value),
    "verify": lambda ctx, value, digest: hash_of(value) == digest,
    "evidence": lambda ctx, seq: (
        ctx.entries[seq]["body"].get("evidence", [])
        if 0 <= _int(seq, "evidence") < len(ctx.entries) else []),
    "def": lambda ctx, name: (
        ctx.state.dictionary[name][-1]["definition"]
        if ctx.state.dictionary.get(name) else {}),
}


def _divmod(ctx, a, b):
    a = _int(a, "div/mod")
    b = _int(b, "div/mod")
    if b == 0:
        raise Refusal("FIELD", "division by zero")
    return (a // b, a % b)
