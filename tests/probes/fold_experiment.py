"""Probe A, rung 5 candidate (measured, not advocated): an
``any`` fold form for the dictionary, quarantined here.

``FoldDictionary`` subclasses ``jacquard.dictionary.Dictionary``
adding ONE token form, ``{"any": [tokens]}``:

- Runtime (``_exec``): the token pops a list. For each element
  it runs ``tokens`` on a FRESH COPY of the remaining stack with
  the element pushed on top -- so the pre-``any`` stack stays
  under the element, and a per-element predicate can also see
  values carried there (for booking clearance: the candidate).
  The per-element run must leave exactly one bool and nothing
  else; the token then pushes ``any`` of those bools onto the
  (untouched) remaining stack. Empty list -> False.
- Simulation (``_simulate``): the same shape rule, on types:
  the per-element tokens are simulated from the remaining
  stack types plus one ``map`` element and must leave exactly
  ``["bool"]``.

What is deliberately NOT overridden: ``computed_effects`` and
the stock ``jacquard.dictionary._walk_tokens`` it walks with.
The stock walk descends into ``if``/``else`` only, so a Tier-E
verb hidden inside ``{"any": [...]}`` is invisible to computed
effects -- the C2 hazard, demonstrated in test_probe_a.py.
``descending_walk_tokens`` below is the patched walk the test
monkeypatches in to show the verb being caught once the walk
descends into ``any`` too.

On top of ``any`` this module builds the booking clearance the
sense computes, but over a LIST-valued unit ``bookings/<box>``
(a list of booking maps):

- ``pair-contends`` (stock tokens only, (map, map) -> bool):
  candidate (bottom) vs committed booking (top), expressing the
  full reference rule -- including the candidate-id identity
  skip, which it CAN express because it receives the whole
  candidate map (the contention sense's subject grammar cannot
  carry the id). Gates are nested ``if``\\ s: each gate computes
  its condition with both maps preserved beneath it; failure
  drops both and answers False.
- ``booking-clear-list`` ((map) -> bool): builds the unit name
  from the candidate's box, reads the list (a missing unit
  normalises to []), runs ``{"any": ["pair-contends"]}`` and
  negates.
"""
import copy

from jacquard import make_envelope
from jacquard.dictionary import Dictionary, _unify
from jacquard.state import Refusal

EXCLUSIVE_SEATS = ["zcode", "mcode", "claude-code", "gpu", "stage",
                   "kimi", "box"]


def descending_walk_tokens(tokens):
    """_walk_tokens, plus descending into "any" token lists."""
    for token in tokens:
        yield token
        if isinstance(token, dict):
            for key in ("if", "else", "any"):
                if key in token:
                    yield from descending_walk_tokens(token.get(key) or [])


class FoldDictionary(Dictionary):
    # ------------------------------------------------ simulation
    def _simulate(self, tokens, stack, defn_name):
        for token in tokens:
            if isinstance(token, dict) and "any" in token:
                if not stack:
                    raise Refusal("FIELD", "%s: any with empty stack"
                                  % defn_name)
                top = stack.pop()
                if _unify(top, "list") is None:
                    raise Refusal("FIELD", "%s: any over %s, not a list"
                                  % (defn_name, top))
                simulated = self._simulate(token.get("any") or [],
                                           list(stack) + ["map"],
                                           defn_name)
                if len(simulated) != 1 \
                        or _unify(simulated[0], "bool") is None:
                    raise Refusal(
                        "FIELD",
                        "%s: any element tokens must leave exactly "
                        "one bool, they leave %s"
                        % (defn_name, simulated))
                stack.append("bool")
            else:
                stack = super()._simulate([token], stack, defn_name)
        return stack

    # ------------------------------------------------ evaluation
    def _exec(self, tokens, stack, requests, ctx, refs):
        for token in tokens:
            if isinstance(token, dict) and "any" in token:
                if not stack:
                    raise Refusal("FIELD", "any with empty stack")
                xs = stack.pop()
                if not isinstance(xs, list):
                    raise Refusal("FIELD", "any expects a list, got %r"
                                  % (xs,))
                rest = list(stack)
                result = False
                for element in xs:
                    element_stack = list(rest) + [copy.deepcopy(element)]
                    self._exec(token.get("any") or [], element_stack,
                               requests, ctx, refs)
                    if len(element_stack) != 1 \
                            or not isinstance(element_stack[0], bool):
                        raise Refusal(
                            "FIELD",
                            "any element tokens must leave exactly "
                            "one bool, they left %r" % (element_stack,))
                    result = result or element_stack[0]
                stack.append(result)
            else:
                super()._exec([token], stack, requests, ctx, refs)


# ------------------------------------------------------ pair predicate

_DROP2_FALSE = ["drop", "drop", {"lit": False}]


def _field_eq_gate(field, negate):
    """[C, O] -> [C, O, C.field != O.field (or ==, if negate is
    False)]. C's field is extracted first via `over` (C sits
    under O), then O's via `over` again (O sits under the first
    extracted value)."""
    tokens = ["over", {"lit": field}, "getf",
              "over", {"lit": field}, "getf", "eq"]
    if negate:
        tokens.append("not")
    return tokens


_GATE_ID = _field_eq_gate("id", negate=True)        # identity skip
_GATE_PRODUCER = _field_eq_gate("producer", negate=True)  # renewal
_GATE_STATUS = ["dup", {"lit": "status"}, "getf",
                {"lit": "active"}, "eq"]
# checkby: None, or >= candidate start. Extract candidate start,
# then the committed checkby, then branch on (checkby is None).
_GATE_CHECKBY = [
    "over", {"lit": "start"}, "getf",
    "over", {"lit": "checkby"}, "getf",
    "dup", {"lit": None}, "eq",
    {"if": ["drop", "drop", {"lit": True}],
     "else": ["swap", "lt", "not"]}]
# seats: equal -> membership of the exclusive set; otherwise
# contention iff either seat is "box".
_GATE_SEAT = [
    "over", {"lit": "seat"}, "getf",
    "over", {"lit": "seat"}, "getf",
    "over", "over", "eq",
    {"if": ["drop", {"lit": EXCLUSIVE_SEATS}, "swap", "contains"],
     "else": ["over", {"lit": "box"}, "eq",
              {"if": ["drop", "drop", {"lit": True}],
               "else": ["swap", "drop", {"lit": "box"}, "eq"]}]}]
# strict overlap, both directions, as a nested gate: the first
# comparison gates the second; its else leaves [C, O, False] so
# both branches of the internal `if` have the same shape.
_GATE_OVERLAP = [
    "over", {"lit": "start"}, "getf",
    "over", {"lit": "end"}, "getf", "lt",
    {"if": ["over", {"lit": "end"}, "getf",
            "over", {"lit": "start"}, "getf", "swap", "lt"],
     "else": [{"lit": False}]}]


def _booking(id_, producer, seat, start, end, checkby=None,
             status="active", rank=0, box="thor"):
    return {"id": id_, "box": box, "producer": producer,
            "seat": seat, "start": start, "end": end,
            "checkby": checkby, "status": status, "rank": rank}


def pair_contends_definition():
    """(map, map) -> bool: candidate (bottom) vs a committed
    booking (top). Stock tokens only -- this word also defines
    on the unmodified dictionary."""
    suffix = _GATE_OVERLAP + ["swap", "drop", "swap", "drop"]
    for gate in reversed([_GATE_ID, _GATE_PRODUCER, _GATE_STATUS,
                          _GATE_CHECKBY, _GATE_SEAT]):
        suffix = gate + [{"if": suffix, "else": list(_DROP2_FALSE)}]
    cand = _booking("c", "lane-b", "gpu", 1100, 1300)
    examples = []
    for other, expect in [
            (_booking("o", "lane-a", "gpu", 1000, 1200), True),
            (_booking("o", "lane-a", "gpu", 1000, 1100), False),
            (_booking("o", "lane-b", "gpu", 1000, 1200), False),
            (_booking("c", "lane-a", "gpu", 1000, 1200), False),
            (_booking("o", "lane-a", "gpu", 1000, 1200,
                      status="done"), False),
            (_booking("o", "lane-a", "gpu", 1000, 1200,
                      checkby=1050), False),
            (_booking("o", "lane-a", "box", 1000, 1200), True),
            (_booking("o", "lane-a", "zcode", 1000, 1200), False)]:
        examples.append({"args": [cand, other], "expect": [expect]})
    return {"name": "pair-contends",
            "signature": {"ins": ["map", "map"], "outs": ["bool"]},
            "body": suffix, "examples": examples}


def booking_clear_list_definition():
    """(map) -> bool over the list-valued unit bookings/<box>."""
    contending = _booking("o", "lane-a", "gpu", 1000, 1200)
    disjoint = _booking("o", "lane-a", "gpu", 2000, 2200)
    cand = _booking("c", "lane-b", "gpu", 1100, 1300)
    return {
        "name": "booking-clear-list",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["dup", {"lit": "box"}, "getf",
                 {"lit": "bookings/"}, "swap", "cat", "get",
                 "dup", {"lit": None}, "eq",
                 {"if": ["drop", {"lit": []}], "else": []},
                 {"any": ["pair-contends"]},
                 "not", "swap", "drop"],
        "examples": [
            {"args": [cand],
             "state": {"units": {"bookings/thor": [contending]}},
             "expect": [False]},
            {"args": [cand],
             "state": {"units": {"bookings/thor": [disjoint]}},
             "expect": [True]},
            {"args": [cand], "state": {"units": {}}, "expect": [True]}]}


def install_fold(seq):
    """Replace the sequencer's dictionary with a FoldDictionary
    and define pair-contends + booking-clear-list on it.
    Returns the sequencer."""
    seq.dictionary = FoldDictionary(
        seq.state, lambda: seq.log.entries, lambda: seq.tentative,
        seq._record_lookup)
    for defn in (pair_contends_definition(),
                 booking_clear_list_definition()):
        verdict = seq.submit(make_envelope(
            "operator", "definition", defn, [],
            "probe-a-fold-def-" + defn["name"]))
        if verdict["status"] != "accepted":
            raise RuntimeError("fold definition %s refused: %r"
                               % (defn["name"], verdict))
    return seq


# ------------------------------------------------- list-layout routing
# Routing only, like booking_flow: the predicate lives in the
# words above; these helpers just write the list-valued units.

def commit_booking_list(seq, lists, booking):
    """Append a booking to its box's list unit bookings/<box>,
    rewriting the whole list (that rewrite IS the layout cost
    measured in the test). `lists` is the caller's mirror of
    what it has written, box -> [booking, ...]."""
    box = booking["box"]
    new_list = list(lists.get(box, [])) + [copy.deepcopy(booking)]
    verdict = seq.submit(make_envelope(
        booking["producer"], "proposal",
        {"class": "booking",
         "requests": [{"verb": "write",
                       "args": ["bookings/%s" % box, new_list]}]},
        ["write"], "probe-a-list-%s-%d" % (booking["id"],
                                           len(seq.log.entries))))
    if verdict.get("outcome") == "allow":
        lists[box] = new_list
    return verdict


def set_booking_list_status(seq, lists, box, booking_id, new_status):
    """Rewrite the box's list with one element's status replaced."""
    new_list = [{**b, "status": new_status} if b["id"] == booking_id
                else dict(b) for b in lists.get(box, [])]
    verdict = seq.submit(make_envelope(
        "operator", "proposal",
        {"class": "booking",
         "requests": [{"verb": "write",
                       "args": ["bookings/%s" % box, new_list]}]},
        ["write"], "probe-a-list-status-%s-%d" % (booking_id,
                                                  len(seq.log.entries))))
    if verdict.get("outcome") == "allow":
        lists[box] = new_list
    return verdict


def evaluate_clear_list(seq, candidate):
    """-> bool: booking-clear-list's answer for a candidate."""
    stack, _requests = seq.evaluate_word(
        "booking-clear-list", "operator", [copy.deepcopy(candidate)])
    assert len(stack) == 1 and isinstance(stack[0], bool), stack
    return stack[0]
