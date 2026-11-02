"""Probe B (Phase 4, F2a): conditional starts at rung 2 (data).

Question: can "starts when X lands" be a wait-condition carried
on the proposal itself -- a pure guard word over committed state,
re-evaluated by the sequencer on each new commit (here: whenever
``pump`` is called) -- instead of rung 1, where an external
watcher / standing rule notices the condition and submits the
proposal, leaving the log unable to say what was being waited
for or why the proposal started?

This module is a PROTOTYPE. It lives in tests/probes/, edits no
kernel code, and models the sequencer change the implementation
slice would make inside ``Sequencer._submit_proposal``'s queued
branch. Every decision-relevant evaluation is done by kernel
machinery: guard truth is ALWAYS a dictionary word evaluated by
``Sequencer.evaluate_word``; the code here only routes (queues,
then asks the kernel's own ``release_queued`` / ``expire_queued``
to act). The prototype necessarily uses kernel-private methods;
the test module's report lists exactly which ones, because those
are the seams a real implementation would internalise.

Wait spec (the rung-2 data)::

    wait = {"guard": <word name>, "deadline_seq": <int>}

``guard`` must resolve in the dictionary to a word of signature
(map -> bool) with empty computed effects -- the same rules the
machine checker applies to transition guards (machines.py:
signature (map -> bool), guard must be pure). ``deadline_seq``
is an absolute log length: the waiter expires once
``len(seq.log.entries) > deadline_seq`` and the guard is still
false. Note that this counts ALL log growth, including the
waiter's own queueing entries (decision + lifecycle
transitions); tests pin that literal reading.

Semantics pinned here (see test_probe_b.py, esp. S3b): the
guard reads CURRENT committed state at re-evaluation time. It
is state-based, not edge-based: if X lands and is then retracted
by a compensating write before the pump runs, the waiter does
NOT start.
"""
import copy

from jacquard import envelope_hash, make_envelope
from jacquard.envelope import validate_envelope
from jacquard.policy import POLICY_VERSION
from jacquard.state import Refusal


# ------------------------------------------------------ guard word

def make_guard_defn(unit, name=None, status_field="status",
                    landed_value="landed"):
    """A (map -> bool) guard word: true iff the committed unit
    `unit` exists and its `status_field` equals `landed_value`.

    One word per artefact is the parameterisation chosen for
    this probe (e.g. `x-landed` for "artifact/x", `y-landed`
    for "artifact/y"): ``make_guard_defn("artifact/y")`` derives
    the name "y-landed".

    Construction, per the probe brief: presence is tested with
    keys+contains (``get`` on a missing unit returns None, and
    ``getf`` on None would crash, so the value is only read
    inside the {"if": ...} branch where presence is known):

    - drop the payload (it is ignored: the guard is over
      committed state, not over the proposal);
    - push the unit name twice (dup), turn one copy into the
      list of committed keys with that prefix (keys), swap and
      test exact membership (contains) -> presence bool;
    - if present: get the unit, getf the status field, eq the
      landed value; else: literal False.

    Genuine examples are included and are checked by the kernel
    at define time: landed -> True, missing -> False, present
    with another status -> False, and a different payload with
    the same state -> True (payload really is ignored).
    """
    if name is None:
        base = unit.rstrip("/").split("/")[-1] or "unit"
        name = "%s-landed" % base
    body = [
        "drop",
        {"lit": unit}, "dup", "keys", "swap", "contains",
        {"if": [{"lit": unit}, "get",
                {"lit": status_field}, "getf",
                {"lit": landed_value}, "eq"],
         "else": [{"lit": False}]},
    ]
    examples = [
        {"args": [{"proposal_id": "example-landed"}],
         "state": {"units": {unit: {status_field: landed_value}}},
         "expect": [True]},
        {"args": [{"proposal_id": "example-missing"}],
         "state": {"units": {}},
         "expect": [False]},
        {"args": [{"proposal_id": "example-retracted"}],
         "state": {"units": {unit: {status_field: "retracted"}}},
         "expect": [False]},
        {"args": [{"completely": "different payload"}],
         "state": {"units": {unit: {status_field: landed_value}}},
         "expect": [True]},
    ]
    return {"name": name,
            "signature": {"ins": ["map"], "outs": ["bool"]},
            "body": body, "examples": examples}


#: The scenario guard from the brief: "artifact/x" has landed.
X_LANDED = make_guard_defn("artifact/x", "x-landed")


def define_guard(seq, defn):
    """Submit a definition envelope for a guard word."""
    return seq.submit(make_envelope(
        "operator", "definition", copy.deepcopy(defn), [],
        "def-" + defn["name"]))


# ------------------------------------------------------ validation

def _validate_guard(seq, guard):
    """Mirror the machine checker's guard rules. Raises Refusal
    before anything is appended when the word does not resolve,
    has the wrong signature, or has computed effects."""
    resolved = seq.dictionary._resolve(guard)
    if resolved is None or resolved[0] != "word":
        raise Refusal("SPEC", "wait guard is not a dictionary "
                              "word: %s" % (guard,))
    _kind, ins, outs, _entry_hash, definition = resolved
    if ins != ["map"] or outs != ["bool"]:
        raise Refusal("FIELD", "wait guard %s must have signature "
                               "(map -> bool), has (%s -> %s)"
                               % (guard, ins, outs))
    effects = seq.dictionary.computed_effects(definition)
    if effects:
        raise Refusal("SPEC", "wait guard %s must be pure, its "
                              "computed effects are %s"
                              % (guard, sorted(effects)))


def _guard_is_true(seq, guard, producer, proposal_id):
    """Evaluate the guard with kernel machinery only. The word
    must leave exactly [True] or [False] and emit no requests."""
    stack, requests = seq.evaluate_word(
        guard, producer, [{"proposal_id": proposal_id}])
    if requests:
        raise Refusal("SPEC", "wait guard %s emitted requests %r"
                              % (guard, requests))
    if stack == [True]:
        return True
    if stack == [False]:
        return False
    raise Refusal("FIELD", "wait guard %s must leave exactly one "
                           "bool, got %r" % (guard, stack))


# ------------------------------------------------------ submission

def submit_waiting(seq, envelope, wait):
    """Queue `envelope` until its wait guard is true, or return
    {"status": "immediate"} if the guard is already true (the
    caller then submits the envelope through the normal path).

    Mirrors ``Sequencer._submit_proposal``'s queued branch,
    plus the wait spec: compute the envelope hash, run
    ``seq._check_requests``, compute effects from the requests
    (plus the irreversible flag), append the decision entry
    carrying requests / irreversible / uses / wait via
    ``seq.log.append``, refold, then step the proposal
    lifecycle (submit, then hold) via ``seq._lifecycle`` -- and,
    as in the kernel's queued branch, create the approval
    instance when that machine is installed.

    Guard validation happens FIRST, before anything is
    appended: a missing, wrongly-signed or impure guard raises
    Refusal with the log untouched. (Simplification, stated
    plainly: an underdeclared envelope returns a REFUSED verdict
    without the kernel's fault decision entry; every scenario
    here uses a correctly declared envelope, and a real slice
    inside _submit_proposal would inherit the kernel's exact
    underdeclared path for free.)
    """
    if not isinstance(wait, dict) \
            or not isinstance(wait.get("guard"), str) \
            or not isinstance(wait.get("deadline_seq"), int) \
            or isinstance(wait.get("deadline_seq"), bool):
        raise Refusal("FIELD", "wait must be {\"guard\": <word "
                               "name>, \"deadline_seq\": <int>}")
    guard = wait["guard"]
    _validate_guard(seq, guard)

    problem = validate_envelope(envelope)
    if problem is not None:
        return {"status": "REFUSED", "refusal": problem[0],
                "detail": problem[1]}
    if envelope["kind"] != "proposal":
        return {"status": "REFUSED", "refusal": "FIELD",
                "detail": "wait applies to proposal envelopes only"}

    producer = envelope["producer"]
    body = envelope["body"]
    if not isinstance(body, dict):
        return {"status": "REFUSED", "refusal": "FIELD",
                "detail": "proposal body must be an object"}
    env_hash = envelope_hash(envelope)

    requests = body.get("requests")
    problem = seq._check_requests(requests)
    if problem is not None:
        return {"status": "REFUSED", "refusal": problem[0],
                "detail": problem[1], "proposal_id": env_hash}

    effects = set()
    for request in requests:
        effects.add(request["verb"])
    if body.get("irreversible"):
        effects.add("irreversible")
    declared = set(envelope["declared_effects"])
    if not effects <= declared:
        return {"status": "REFUSED", "refusal": "UNDERDECLARED",
                "detail": ("declared effects %s do not cover actual "
                           "effects %s"
                           % (sorted(declared), sorted(effects))),
                "proposal_id": env_hash}

    # Already true at submission: queue nothing at all.
    if _guard_is_true(seq, guard, producer, env_hash):
        return {"status": "immediate", "proposal_id": env_hash}

    cls = body.get("class", "work")
    decision = {"producer": producer, "class": cls,
                "proposal_id": env_hash,
                "policy_version": POLICY_VERSION,
                "outcome": "queued",
                "reasons": ["waiting:%s" % guard],
                "effects": sorted(effects),
                "requests": requests,
                "irreversible": bool(body.get("irreversible")),
                "uses": body.get("uses", []),
                "wait": copy.deepcopy(wait)}
    seq.log.append("decision", decision)
    seq._refold()
    seq._lifecycle("proposal", env_hash, "submit", producer)
    seq._lifecycle("proposal", env_hash, "hold", producer)
    if seq._machine_definition("approval") is not None:
        seq.create_machine_instance(
            "approval", "approval:" + env_hash, producer)
    seq._refold()
    return {"status": "decided", "outcome": "queue",
            "proposal_id": env_hash,
            "reasons": ["waiting:%s" % guard]}


# ------------------------------------------------------ re-evaluation

def pump(seq, actor="wait-pump"):
    """Re-evaluate every waiting proposal against CURRENT
    committed state, in decision-queue order, until a full pass
    changes nothing (bounded at 10 passes).

    For each queue entry carrying a "wait" field (snapshot in
    queue order): guard true -> ``seq.release_queued`` and
    record ("released", id); else, once the log has grown past
    the deadline, ``seq.expire_queued`` and record
    ("expired", id). release/expire write their own fixed
    reasons ("released-by-operator" / "expired-in-queue") --
    that is fine: the wait guard's name is already in the
    queueing decision entry, which is what the audit in S7
    reads. Returns the list of actions taken, in order.
    """
    actions = []
    for _pass in range(10):
        changed = False
        snapshot = [(proposal_id, dict(body))
                    for proposal_id, body
                    in seq.state.decision_queue.items()
                    if isinstance(body.get("wait"), dict)]
        for proposal_id, queued in snapshot:
            if proposal_id not in seq.state.decision_queue:
                continue  # acted on earlier in this same pass
            wait = queued["wait"]
            if _guard_is_true(seq, wait["guard"],
                              queued["producer"], proposal_id):
                result = seq.release_queued(proposal_id, actor)
                if result.get("status") == "decided":
                    actions.append(("released", proposal_id))
                    changed = True
            elif len(seq.log.entries) > wait["deadline_seq"]:
                result = seq.expire_queued(proposal_id, actor)
                if result.get("status") == "decided":
                    actions.append(("expired", proposal_id))
                    changed = True
        if not changed:
            break
    return actions
