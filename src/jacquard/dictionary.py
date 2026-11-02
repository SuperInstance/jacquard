"""Definitions and the dictionary (SPEC section 5).

A definition's effects are computed from its parts, never taken
from its author. Definitions reference primitives and previously
defined words only, so the reference graph is acyclic and
expansion terminates. Stored definitions pin the entry hash of
every word they reference, so redefining a word never changes
what an existing definition does.
"""
import copy

from .primitives import (PRIMITIVES, SYNTAX_FORMS, TIER_E, IMPLS,
                         EvalContext)
from .state import Refusal

TYPES = ("val", "int", "bool", "str", "list", "map")


def type_of(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return "val"


def _unify(a, b):
    """Return the common type or None. `val` unifies with anything."""
    if a == b:
        return a
    if a == "val":
        return b
    if b == "val":
        return a
    return None


def _walk_tokens(tokens):
    for token in tokens:
        yield token
        if isinstance(token, dict) and "if" in token:
            yield from _walk_tokens(token.get("if") or [])
            yield from _walk_tokens(token.get("else") or [])


class Dictionary:
    def __init__(self, state, get_entries, get_tentative=None,
                 record_lookup=None):
        self.state = state
        self.get_entries = get_entries
        self.get_tentative = get_tentative or (lambda: {})
        self.record_lookup = record_lookup

    # ------------------------------------------------ resolution
    def _resolve(self, name):
        """-> (kind, ins, outs, entry_hash, definition) or None."""
        if name in PRIMITIVES:
            spec = PRIMITIVES[name]
            return ("primitive", spec["ins"], spec["outs"], None, None)
        versions = self.state.dictionary.get(name)
        if versions:
            latest = versions[-1]
            defn = latest["definition"]
            return ("word", defn["signature"]["ins"],
                    defn["signature"]["outs"], latest["entry_hash"], defn)
        return None

    def _version_by_hash(self, name, entry_hash):
        for version in self.state.dictionary.get(name, []):
            if version["entry_hash"] == entry_hash:
                return version["definition"]
        return None

    # ------------------------------------------------ effects
    def computed_effects(self, defn, _seen=None):
        effects = set()
        seen = _seen if _seen is not None else set()
        for token in _walk_tokens(defn["body"]):
            if not isinstance(token, str):
                continue
            if token in TIER_E:
                effects.add(token)
            elif token not in PRIMITIVES and token not in SYNTAX_FORMS:
                resolved = self._resolve(token)
                if resolved and resolved[0] == "word":
                    key = resolved[3]
                    if key not in seen:
                        seen.add(key)
                        effects |= self.computed_effects(resolved[4], seen)
        return effects

    # ------------------------------------------------ define
    def define(self, defn):
        for field in ("name", "signature", "body", "examples"):
            if field not in defn:
                raise Refusal("FIELD", "definition missing field: %s" % field)
        sig = defn["signature"]
        if "ins" not in sig or "outs" not in sig:
            raise Refusal("FIELD", "signature needs ins and outs")
        for t in list(sig["ins"]) + list(sig["outs"]):
            if t not in TYPES:
                raise Refusal("FIELD", "unknown type in signature: %r" % (t,))
        # Reference existence (SPEC)
        refs = {}
        for token in _walk_tokens(defn["body"]):
            if isinstance(token, str) and token not in PRIMITIVES \
                    and token not in SYNTAX_FORMS:
                resolved = self._resolve(token)
                if resolved is None or resolved[0] != "word":
                    raise Refusal("SPEC", "unknown reference: %s" % token)
                refs[token] = resolved[3]
        self._check_signature(defn)
        effects = self.computed_effects(defn)
        declared = defn.get("declared_effects")
        if declared is not None and set(declared) != effects:
            raise Refusal(
                "UNDERDECLARED",
                "declared effects %s do not equal computed effects %s"
                % (sorted(set(declared)), sorted(effects)))
        self._check_examples(defn)
        stored = {"name": defn["name"], "signature": defn["signature"],
                  "body": defn["body"], "examples": defn["examples"],
                  "refs": refs, "computed_effects": sorted(effects)}
        return stored

    # ------------------------------------------------ signature check
    def _simulate(self, tokens, stack, defn_name):
        for token in tokens:
            if isinstance(token, dict) and "lit" in token:
                stack.append(type_of(token["lit"]))
            elif isinstance(token, dict) and "if" in token:
                if not stack:
                    raise Refusal("FIELD", "%s: if with empty stack" % defn_name)
                cond = stack.pop()
                if _unify(cond, "bool") is None:
                    raise Refusal("FIELD", "%s: if condition is %s, not bool"
                                  % (defn_name, cond))
                then_stack = self._simulate(token.get("if") or [], list(stack),
                                            defn_name)
                else_stack = self._simulate(token.get("else") or [], list(stack),
                                            defn_name)
                if len(then_stack) != len(else_stack) or any(
                        _unify(a, b) is None
                        for a, b in zip(then_stack, else_stack)):
                    raise Refusal(
                        "FIELD",
                        "%s: if branches leave different stack shapes (%s vs %s)"
                        % (defn_name, then_stack, else_stack))
                stack[:] = then_stack
            elif isinstance(token, str) and token in SYNTAX_FORMS:
                self._simulate_syntax(token, stack, defn_name)
            elif isinstance(token, str):
                resolved = self._resolve(token)
                if resolved is None:
                    raise Refusal("SPEC", "unknown reference: %s" % token)
                _, ins, outs, _, _ = resolved
                if len(stack) < len(ins):
                    raise Refusal("FIELD", "%s: stack underflow at %s"
                                  % (defn_name, token))
                args = stack[len(stack) - len(ins):]
                del stack[len(stack) - len(ins):]
                for want, got in zip(ins, args):
                    if _unify(want, got) is None:
                        raise Refusal(
                            "FIELD",
                            "%s: %s expects %s, stack has %s"
                            % (defn_name, token, ins, args))
                stack.extend(outs)
            else:
                raise Refusal("FIELD", "%s: bad token %r" % (defn_name, token))
        return stack

    def _simulate_syntax(self, token, stack, defn_name):
        def need(n):
            if len(stack) < n:
                raise Refusal("FIELD", "%s: stack underflow at %s"
                              % (defn_name, token))
        if token == "dup":
            need(1)
            stack.append(stack[-1])
        elif token == "drop":
            need(1)
            stack.pop()
        elif token == "swap":
            need(2)
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif token == "over":
            need(2)
            stack.append(stack[-2])
        elif token == "snoc":
            need(2)
            value = stack.pop()
            xs = stack.pop()
            if _unify(xs, "list") is None:
                raise Refusal("FIELD", "%s: snoc on %s" % (defn_name, xs))
            stack.append("list")
        elif token == "assoc":
            need(3)
            stack.pop()
            key = stack.pop()
            m = stack.pop()
            if _unify(m, "map") is None or _unify(key, "str") is None:
                raise Refusal("FIELD", "%s: assoc on %s/%s"
                              % (defn_name, m, key))
            stack.append("map")
        elif token == "getf":
            need(2)
            key = stack.pop()
            m = stack.pop()
            if _unify(m, "map") is None or _unify(key, "str") is None:
                raise Refusal("FIELD", "%s: getf on %s/%s"
                              % (defn_name, m, key))
            stack.append("val")
        elif token == "first":
            need(1)
            xs = stack.pop()
            if _unify(xs, "list") is None:
                raise Refusal("FIELD", "%s: first on %s" % (defn_name, xs))
            stack.append("val")
        elif token == "cat":
            need(2)
            b = stack.pop()
            a = stack.pop()
            if _unify(a, "str") is None or _unify(b, "str") is None:
                raise Refusal("FIELD", "%s: cat on %s/%s" % (defn_name, a, b))
            stack.append("str")

    def _check_signature(self, defn):
        stack = list(defn["signature"]["ins"])
        result = self._simulate(defn["body"], stack, defn["name"])
        outs = defn["signature"]["outs"]
        if len(result) != len(outs) or any(
                _unify(a, b) is None for a, b in zip(result, outs)):
            raise Refusal(
                "FIELD",
                "%s: body leaves stack %s, signature promises %s"
                % (defn["name"], result, outs))

    # ------------------------------------------------ examples
    def _check_examples(self, defn):
        from .state import State
        for i, example in enumerate(defn.get("examples", [])):
            state = State()
            given = example.get("state") or {}
            state.units.update(copy.deepcopy(given.get("units") or {}))
            state.senses.update(copy.deepcopy(given.get("senses") or {}))
            ctx = EvalContext(state, self.get_entries(), "example",
                              self.get_tentative(), self.record_lookup)
            # Evaluate the candidate body directly (it is not in the
            # dictionary yet); word refs resolve against the current
            # dictionary, pinned by the refs gathered in define().
            refs = {}
            for token in _walk_tokens(defn["body"]):
                if isinstance(token, str) and token not in PRIMITIVES \
                        and token not in SYNTAX_FORMS:
                    resolved = self._resolve(token)
                    if resolved and resolved[0] == "word":
                        refs[token] = resolved[3]
            try:
                stack, requests = self._run(
                    defn["body"], list(example.get("args", [])), ctx, refs)
            except Refusal as refusal:
                raise Refusal("EXAMPLE", "example %d: evaluation refused: %s"
                              % (i, refusal.detail))
            if "expect" in example and stack != example["expect"]:
                raise Refusal(
                    "EXAMPLE",
                    "example %d: expected final stack %r, got %r"
                    % (i, example["expect"], stack))
            if "requests" in example:
                verbs = [r["verb"] for r in requests]
                if verbs != list(example["requests"]):
                    raise Refusal(
                        "EXAMPLE",
                        "example %d: expected requests %r, got %r"
                        % (i, example["requests"], verbs))

    # ------------------------------------------------ evaluation
    def evaluate(self, name, args, ctx):
        versions = self.state.dictionary.get(name)
        if not versions:
            raise Refusal("SPEC", "no such definition: %s" % name)
        defn = versions[-1]["definition"]
        return self._run(defn["body"], list(args), ctx,
                         defn.get("refs") or {})

    def _run(self, tokens, stack, ctx, refs):
        requests = []
        self._exec(tokens, stack, requests, ctx, refs)
        return stack, requests

    def _exec(self, tokens, stack, requests, ctx, refs):
        for token in tokens:
            if isinstance(token, dict) and "lit" in token:
                stack.append(copy.deepcopy(token["lit"]))
            elif isinstance(token, dict) and "if" in token:
                if not stack:
                    raise Refusal("FIELD", "if with empty stack")
                branch = token.get("if") if stack.pop() else token.get("else")
                self._exec(branch or [], stack, requests, ctx, refs)
            elif isinstance(token, str) and token in SYNTAX_FORMS:
                self._exec_syntax(token, stack)
            elif isinstance(token, str) and token in PRIMITIVES:
                spec = PRIMITIVES[token]
                n = len(spec["ins"])
                if len(stack) < n:
                    raise Refusal("FIELD", "stack underflow at %s" % token)
                args = stack[len(stack) - n:]
                del stack[len(stack) - n:]
                if spec["tier"] == "E":
                    requests.append({"verb": token, "args": args})
                else:
                    stack.append(IMPLS[token](ctx, *args))
            elif isinstance(token, str):
                defn = None
                if token in refs:
                    defn = self._version_by_hash(token, refs[token])
                if defn is None:
                    versions = self.state.dictionary.get(token)
                    if versions:
                        defn = versions[-1]["definition"]
                if defn is None:
                    raise Refusal("SPEC", "unknown reference: %s" % token)
                self._exec(defn["body"], stack, requests, ctx,
                           defn.get("refs") or {})
            else:
                raise Refusal("FIELD", "bad token %r" % (token,))

    def _exec_syntax(self, token, stack):
        def need(n):
            if len(stack) < n:
                raise Refusal("FIELD", "stack underflow at %s" % token)
        if token == "dup":
            need(1)
            stack.append(stack[-1])
        elif token == "drop":
            need(1)
            stack.pop()
        elif token == "swap":
            need(2)
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif token == "over":
            need(2)
            stack.append(stack[-2])
        elif token == "snoc":
            need(2)
            value = stack.pop()
            xs = stack.pop()
            stack.append(list(xs) + [value])
        elif token == "assoc":
            need(3)
            value = stack.pop()
            key = stack.pop()
            m = stack.pop()
            merged = dict(m)
            merged[key] = value
            stack.append(merged)
        elif token == "getf":
            need(2)
            key = stack.pop()
            m = stack.pop()
            stack.append(m.get(key))
        elif token == "first":
            need(1)
            xs = stack.pop()
            if not xs:
                raise Refusal("FIELD", "first of empty list")
            stack.append(xs[0])
        elif token == "cat":
            need(2)
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b)
