"""Lifecycle machines: the machine profile (SPEC section 10).

A machine definition is text — one directive per line:

    machine proposal
    initial: received
    terminal: closed, refused
    events: submit, decide, commit, close, hold, refuse
    received -> validated : submit
    validated -> tentative : hold
    validated -> decided : decide
    decided -> committed : commit / note-decision
    committed -> closed : close [is-final]
    ignore refuse in *

Transitions may name a guard word (`[word]`: a dictionary word of
signature (map -> bool) with no computed effects) and an action
word (`/ word`: a dictionary word taking the event payload map,
evaluated for the requests it emits). At most one guarded
transition plus one `otherwise` fallback may share a
(state, event) pair: guard disjointness cannot be proven
statically, so anything more is refused as AMBIGUOUS.

The static checker refuses, by name: FIELD (malformed text, type
errors), SPEC (unknown word or event references), UNREACHABLE
(a state no path from the initial state reaches), DEAD (a
non-terminal state with no outgoing transitions, or one that
cannot reach any declared terminal), AMBIGUOUS, and NON_TOTAL
(a (state, event) pair that neither transitions nor is
explicitly ignored). Machines are flat and total by construction.

This is the repo's own small checker, written for this profile.
It is not StateSmith and does not try to be: the profile is
deliberately smaller (see the builder's log, Phase 2 opening).
"""
import re

from .canonical import hash_of
from .state import Refusal

_TOKEN = r"[A-Za-z0-9_][A-Za-z0-9_-]*"
_TRANSITION = re.compile(
    r"^(%s)\s*->\s*(%s)\s*:\s*(%s)\s*(.*)$" % (_TOKEN, _TOKEN, _TOKEN))
_IGNORE = re.compile(r"^ignore\s+(%s)\s+in\s+(.+)$" % _TOKEN)
_GUARD = re.compile(r"\[\s*(%s)\s*\]" % _TOKEN)
_ACTION = re.compile(r"/\s*(%s)" % _TOKEN)


def _csv(text):
    return [item.strip() for item in text.split(",") if item.strip()]


def parse_machine(text):
    """Parse machine definition text into its stored dict form.

    Raises Refusal(FIELD) on malformed text. Static profile
    checks live in check_machine."""
    if not isinstance(text, str):
        raise Refusal("FIELD", "machine body must be definition text")
    name = None
    initial = None
    terminals = None
    events = None
    declared_states = []
    transitions = []
    ignores = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("machine "):
            if name is not None:
                raise Refusal("FIELD", "line %d: second machine header" % lineno)
            name = line[len("machine "):].strip()
            if not re.fullmatch(_TOKEN, name):
                raise Refusal("FIELD", "line %d: bad machine name" % lineno)
            continue
        if name is None:
            raise Refusal("FIELD", "line %d: directive before machine header"
                          % lineno)
        if line.startswith("initial:"):
            initial = line[len("initial:"):].strip()
        elif line.startswith("terminal:"):
            rest = line[len("terminal:"):].strip()
            terminals = [] if rest == "none" else _csv(rest)
        elif line.startswith("events:"):
            events = _csv(line[len("events:"):])
        elif line.startswith("state "):
            declared_states.append(line[len("state "):].strip())
        elif line.startswith("ignore "):
            match = _IGNORE.match(line)
            if not match:
                raise Refusal("FIELD", "line %d: malformed ignore" % lineno)
            rest = match.group(2).strip()
            states = "*" if rest == "*" else _csv(rest)
            ignores.append({"event": match.group(1), "states": states})
        else:
            match = _TRANSITION.match(line)
            if not match:
                raise Refusal("FIELD", "line %d: cannot parse: %r"
                              % (lineno, raw.strip()))
            frm, to, event, rest = match.groups()
            guard = None
            action = None
            otherwise = False
            found = _GUARD.search(rest)
            if found:
                guard = found.group(1)
                rest = rest[:found.start()] + rest[found.end():]
            found = _ACTION.search(rest)
            if found:
                action = found.group(1)
                rest = rest[:found.start()] + rest[found.end():]
            if "otherwise" in rest.split():
                otherwise = True
                rest = rest.replace("otherwise", "")
            if rest.strip():
                raise Refusal("FIELD", "line %d: trailing junk: %r"
                              % (lineno, rest.strip()))
            transitions.append({"from": frm, "event": event, "to": to,
                                "guard": guard, "action": action,
                                "otherwise": otherwise})
    if name is None:
        raise Refusal("FIELD", "no machine header")
    if initial is None:
        raise Refusal("FIELD", "machine %s: no initial state" % name)
    if terminals is None:
        raise Refusal("FIELD", "machine %s: no terminal declaration" % name)
    if events is None:
        raise Refusal("FIELD", "machine %s: no events declaration" % name)
    states = {initial} | set(terminals) | set(declared_states)
    for transition in transitions:
        states.add(transition["from"])
        states.add(transition["to"])
    for ignore in ignores:
        if ignore["states"] != "*":
            states |= set(ignore["states"])
    return {"name": name, "initial": initial, "terminals": terminals,
            "events": events, "states": sorted(states),
            "transitions": transitions, "ignores": ignores,
            "source_hash": hash_of(text)}


def _coverage(defn):
    """(pairs_with_transition, ignored_pairs) after expanding
    `ignore ... in *` to every state with no transition for the
    event."""
    with_transition = {}
    for transition in defn["transitions"]:
        key = (transition["from"], transition["event"])
        with_transition.setdefault(key, []).append(transition)
    ignored = set()
    for ignore in defn["ignores"]:
        if ignore["states"] == "*":
            for state in defn["states"]:
                if (state, ignore["event"]) not in with_transition:
                    ignored.add((state, ignore["event"]))
        else:
            for state in ignore["states"]:
                ignored.add((state, ignore["event"]))
    return with_transition, ignored


def check_machine(defn, resolve_word):
    """Static profile checks. resolve_word(name) returns
    (ins, outs, computed_effects) for a dictionary word, or None.
    Raises Refusal with the profile's names, in a fixed order:
    FIELD, SPEC, UNREACHABLE, DEAD, AMBIGUOUS, NON_TOTAL."""
    alphabet = set(defn["events"])
    if len(alphabet) != len(defn["events"]):
        raise Refusal("FIELD", "machine %s: duplicate event in alphabet"
                      % defn["name"])
    for terminal in defn["terminals"]:
        if terminal not in defn["states"]:
            raise Refusal("FIELD", "machine %s: terminal %r is not a state"
                          % (defn["name"], terminal))
    seen = set()
    for transition in defn["transitions"]:
        key = (transition["from"], transition["event"], transition["to"],
               transition["guard"], transition["action"],
               transition["otherwise"])
        if key in seen:
            raise Refusal("FIELD", "machine %s: duplicate transition %s"
                          % (defn["name"], key))
        seen.add(key)
        if transition["event"] not in alphabet:
            raise Refusal("FIELD", "machine %s: event %r not in the "
                          "declared alphabet" % (defn["name"],
                                                 transition["event"]))
    for ignore in defn["ignores"]:
        if ignore["event"] not in alphabet:
            raise Refusal("FIELD", "machine %s: ignored event %r not in "
                          "the declared alphabet" % (defn["name"],
                                                     ignore["event"]))
    # SPEC: guards and actions are dictionary words, with the
    # profile's signatures; guards must be effect-free.
    for transition in defn["transitions"]:
        for role, word in (("guard", transition["guard"]),
                           ("action", transition["action"])):
            if word is None:
                continue
            resolved = resolve_word(word)
            if resolved is None:
                raise Refusal("SPEC", "machine %s: unknown %s word: %s"
                              % (defn["name"], role, word))
            ins, outs, effects = resolved
            if role == "guard":
                if ins != ["map"] or outs != ["bool"]:
                    raise Refusal(
                        "FIELD", "machine %s: guard %s must have signature "
                        "(map -> bool), has (%s -> %s)"
                        % (defn["name"], word, ins, outs))
                if effects:
                    raise Refusal(
                        "SPEC", "machine %s: guard %s must be pure, its "
                        "computed effects are %s"
                        % (defn["name"], word, sorted(effects)))
            else:
                if ins != ["map"]:
                    raise Refusal(
                        "FIELD", "machine %s: action %s must take the "
                        "payload map, its inputs are %s"
                        % (defn["name"], word, ins))
    with_transition, ignored = _coverage(defn)
    for (state, event) in sorted(ignored):
        if (state, event) in with_transition:
            raise Refusal("FIELD", "machine %s: %s on %s is both "
                          "transitioned and ignored"
                          % (defn["name"], event, state))
    # UNREACHABLE: breadth-first from the initial state.
    forward = {}
    for transition in defn["transitions"]:
        forward.setdefault(transition["from"], set()).add(transition["to"])
    reached = {defn["initial"]}
    frontier = [defn["initial"]]
    while frontier:
        nxt = []
        for state in frontier:
            for to in forward.get(state, ()):
                if to not in reached:
                    reached.add(to)
                    nxt.append(to)
        frontier = nxt
    for state in defn["states"]:
        if state not in reached:
            raise Refusal("UNREACHABLE", "machine %s: state %s is not "
                          "reachable from %s"
                          % (defn["name"], state, defn["initial"]))
    # DEAD: sinks that are not terminal, and (with terminals
    # declared) states that cannot reach any terminal.
    terminals = set(defn["terminals"])
    for state in defn["states"]:
        if state not in terminals and not forward.get(state):
            raise Refusal("DEAD", "machine %s: state %s has no outgoing "
                          "transitions and is not terminal"
                          % (defn["name"], state))
    if terminals:
        reverse = {}
        for transition in defn["transitions"]:
            reverse.setdefault(transition["to"], set()).add(transition["from"])
        can_reach = set(terminals)
        frontier = list(terminals)
        while frontier:
            nxt = []
            for state in frontier:
                for frm in reverse.get(state, ()):
                    if frm not in can_reach:
                        can_reach.add(frm)
                        nxt.append(frm)
            frontier = nxt
        for state in defn["states"]:
            if state not in can_reach:
                raise Refusal("DEAD", "machine %s: state %s cannot reach "
                              "any terminal state" % (defn["name"], state))
    # AMBIGUOUS: per (state, event), at most one guarded transition
    # plus at most one `otherwise` fallback; a plain unguarded
    # transition must be alone.
    for (state, event), group in sorted(with_transition.items()):
        guarded = [t for t in group if t["guard"]]
        fallback = [t for t in group if t["otherwise"]]
        plain = [t for t in group if not t["guard"] and not t["otherwise"]]
        if len(guarded) > 1:
            raise Refusal("AMBIGUOUS", "machine %s: %s on %s has %d "
                          "guarded transitions; guard disjointness cannot "
                          "be proven statically"
                          % (defn["name"], event, state, len(guarded)))
        if len(fallback) > 1:
            raise Refusal("AMBIGUOUS", "machine %s: %s on %s has two "
                          "otherwise fallbacks" % (defn["name"], event, state))
        if plain and (guarded or fallback):
            raise Refusal("AMBIGUOUS", "machine %s: %s on %s mixes a plain "
                          "transition with guarded/fallback transitions"
                          % (defn["name"], event, state))
        if len(plain) > 1:
            raise Refusal("AMBIGUOUS", "machine %s: %s on %s has %d plain "
                          "transitions" % (defn["name"], event, state,
                                           len(plain)))
    # NON_TOTAL: every (state, event) transitions or is ignored.
    for state in defn["states"]:
        for event in defn["events"]:
            if (state, event) in with_transition:
                continue
            if (state, event) in ignored:
                continue
            raise Refusal("NON_TOTAL", "machine %s: state %s has no "
                          "transition or explicit ignore for event %s"
                          % (defn["name"], state, event))
    return defn


def find_transition(defn, state, event):
    """-> (candidates, ignored). Candidates are ordered: guarded
    transitions in source order, then the `otherwise` fallback.
    The unguarded plain case yields a single candidate."""
    with_transition, ignored = _coverage(defn)
    group = with_transition.get((state, event), [])
    guarded = [t for t in group if t["guard"]]
    plain = [t for t in group if not t["guard"] and not t["otherwise"]]
    fallback = [t for t in group if t["otherwise"]]
    return (guarded + plain + fallback, (state, event) in ignored)
