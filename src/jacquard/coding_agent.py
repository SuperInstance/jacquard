"""The coding-agent profile (Phase 5, slice 12): definitions
and policy data, not kernel code.

A coding agent (the first live host is ZCode) emits four
classes of action. Each class is a dictionary word whose
effects are COMPUTED by the kernel's dictionary machinery from
the Tier-E verbs in its body -- never declared by the adapter:

- ``agent-read``    -- a file read. The word is pure (it uses
  the Tier-P ``get`` view), so its computed effects are empty
  and policy/1 allows the proposal at once: reads fast-path.
- ``agent-write``   -- a file write/edit. The word emits a
  ``write`` request carrying the target unit and the new
  content.
- ``agent-shell``   -- a shell command. The word emits a
  ``dispatch`` request whose action is ``{"cmd": [...]}`` (the
  sandboxed executor's action shape).
- ``agent-network`` -- a network action (fetch/search). The
  word emits a ``send`` request; ``send`` is a policy/1
  protected effect, so these queue on their own effects.

The profile's policy is DATA (``TOOL_CLASSES`` below), read
generically by ``prepare_requests`` / ``submit_tool_action``:
reads fast-path; writes and shell commands queue. Queueing is
expressed the way the booking profile expresses it (spec
section 11.4's flow): a queued class's proposal carries a
``notify`` request alongside its real request, and ``notify``
is a policy/1 protected effect, so the kernel -- not this
module -- makes the queue decision. A class queues "unless a
standing rule covers it": an ACTIVE learner rule whose shape
is (producer, class, effects) and whose predicted outcome is
``allow`` overrides the queue outcome through the sequencer's
rule hook (the learner's ``install``), exactly as for any
other producer. This module contains no per-class decision
branches: the gate column is data, and the kernel decides.

Approvals are consumed once. Releasing a queued proposal
executes its requests against kernel state (the record that
the action was authorised); the host performs the real action
when the adapter next sees the identical action and finds the
unconsumed release in the log (``find_unconsumed_release``).
Consumption is itself a log entry (a sense publication), so
the whole story replays.
"""
import copy

from .canonical import canonical
from .envelope import envelope_hash, make_envelope
from .lifecycles import install_lifecycles

# ---------------------------------------------------------- words

_AGENT_READ = {
    "name": "agent-read",
    "signature": {"ins": ["map"], "outs": ["val"]},
    "body": [{"lit": "path"}, "getf", "get"],
    "examples": [
        {"args": [{"path": "agent/note"}],
         "state": {"units": {"agent/note": "hello"}},
         "expect": ["hello"]},
        {"args": [{"path": "agent/absent"}], "expect": [None]}],
}

_AGENT_WRITE = {
    "name": "agent-write",
    "signature": {"ins": ["map"], "outs": []},
    "body": ["dup", {"lit": "unit"}, "getf", "swap",
             {"lit": "value"}, "getf", "write"],
    "examples": [
        {"args": [{"unit": "agent-file:/tmp/x.py", "value": "print(1)"}],
         "requests": ["write"]}],
}

_AGENT_SHELL = {
    "name": "agent-shell",
    "signature": {"ins": ["map"], "outs": []},
    "body": ["dup", {"lit": "cmd"}, "getf",
             {"lit": {}}, "swap", {"lit": "cmd"}, "swap", "assoc",
             "dispatch", "drop"],
    "examples": [
        {"args": [{"cmd": ["echo", "hi"]}], "requests": ["dispatch"]}],
}

_AGENT_NETWORK = {
    "name": "agent-network",
    "signature": {"ins": ["map"], "outs": []},
    "body": ["dup", {"lit": "channel"}, "getf", "swap",
             {"lit": "payload"}, "getf", "send"],
    "examples": [
        {"args": [{"channel": "https://example.com", "payload": {"q": 1}}],
         "requests": ["send"]}],
}

DEFINITIONS = [_AGENT_READ, _AGENT_WRITE, _AGENT_SHELL, _AGENT_NETWORK]

# The effects the kernel must compute for each word. Install
# refuses the profile if the computed set differs -- the words
# cannot smuggle an effect past this table, and the table
# cannot claim an effect the words do not have.
EXPECTED_EFFECTS = {
    "agent-read": [],
    "agent-write": ["write"],
    "agent-shell": ["dispatch"],
    "agent-network": ["send"],
}

# ---------------------------------------------------------- policy
# The profile's policy content, as data. ``gate`` is the only
# policy knob: "allow" submits the word's requests as they are;
# "queue" appends a notify request (a policy/1 protected
# effect) addressed to ``gate_surface``, so the kernel queues
# the proposal for a batched operator decision unless an
# active standing rule covers the shape. ``agent-network``
# needs no gate request -- ``send`` already queues -- but
# carries the same row shape for uniformity.

TOOL_CLASSES = {
    "agent-read": {"word": "agent-read", "gate": "allow"},
    "agent-write": {"word": "agent-write", "gate": "queue",
                    "gate_surface": "jacquard-approvals"},
    "agent-shell": {"word": "agent-shell", "gate": "queue",
                    "gate_surface": "jacquard-approvals"},
    "agent-network": {"word": "agent-network", "gate": "queue",
                      "gate_surface": "jacquard-approvals"},
}

# The sense name under which approval consumptions are
# published. Each consumption is one sense entry in the log:
# {"proposal_id": ..., "count": <consumptions so far>}.
CONSUMED_SENSE = "zcode-approval-consumption"


def install_coding_agent(seq):
    """Install the coding-agent profile on a sequencer: the
    lifecycle machines and the four tool-class words. Returns
    the verdicts; raises if any submission was refused or a
    word's computed effects differ from EXPECTED_EFFECTS (fail
    loud, never half-installed)."""
    verdicts = {"lifecycles": install_lifecycles(seq),
                "definitions": {}}
    for defn in DEFINITIONS:
        verdict = seq.submit(make_envelope(
            "operator", "definition", copy.deepcopy(defn), [],
            "coding-agent-def-" + defn["name"]))
        verdicts["definitions"][defn["name"]] = verdict
        if verdict["status"] != "accepted":
            raise RuntimeError("definition %s refused: %r"
                               % (defn["name"], verdict))
        expected = EXPECTED_EFFECTS[defn["name"]]
        if verdict["computed_effects"] != expected:
            raise RuntimeError(
                "definition %s computed effects %r, expected %r"
                % (defn["name"], verdict["computed_effects"], expected))
    return verdicts


def profile_installed(seq):
    return all(name in seq.state.dictionary for name in EXPECTED_EFFECTS)


# ---------------------------------------------------------- requests

def prepare_requests(seq, producer, tool_class, payload):
    """Evaluate the class's word against `payload` and apply
    the profile's gate data. Returns the proposal request list.
    The word's emitted requests are the kernel-computed truth
    about what the action does; the gate request (if the class
    queues) is appended here, from the TOOL_CLASSES row."""
    row = TOOL_CLASSES[tool_class]
    _stack, requests = seq.evaluate_word(row["word"], producer,
                                         [copy.deepcopy(payload)])
    requests = [{"verb": r["verb"], "args": r["args"]} for r in requests]
    if row["gate"] == "queue" and tool_class != "agent-network":
        requests.append({
            "verb": "notify",
            "args": [row["gate_surface"],
                     {"class": tool_class,
                      "summary": _summary(tool_class, payload)}]})
    return requests


def _summary(tool_class, payload):
    """A one-line, size-bounded description of the action for
    the operator's queue presentation. Content bodies are NOT
    summarised into the notify artifact beyond their size --
    the full request already sits in the queued decision."""
    if tool_class == "agent-write":
        value = payload.get("value")
        size = len(canonical(value)) if value is not None else 0
        return "write %s (%d bytes of value)" % (payload.get("unit"), size)
    if tool_class == "agent-shell":
        return "run %s" % " ".join(str(p) for p in payload.get("cmd", []))
    if tool_class == "agent-network":
        return "send to %s" % payload.get("channel")
    return tool_class


def submit_tool_action(seq, producer, tool_class, payload, idem):
    """Submit one tool action as a proposal. Returns the
    kernel's verdict dict (with proposal_id and outcome)."""
    requests = prepare_requests(seq, producer, tool_class, payload)
    effects = sorted({r["verb"] for r in requests})
    envelope = make_envelope(
        producer, "proposal",
        {"class": tool_class, "requests": requests},
        effects, idem)
    return seq.submit(envelope)


# ---------------------------------------------------------- log scans
# The adapter's bookkeeping reads. Everything here is derived
# from the log alone, so any of it can be re-derived by replay.

def binding_hash(seq, proposal_id):
    """The hash of the decision entry that queued this item --
    the value an approval binds to (tools/jq.py semantics)."""
    for entry in seq.log.entries:
        body = entry["body"]
        if entry["kind"] == "decision" \
                and body.get("proposal_id") == proposal_id \
                and body.get("outcome") == "queued":
            return entry["hash"]
    return None


def _requests_key(producer, tool_class, requests):
    return canonical({"producer": producer, "class": tool_class,
                      "requests": requests})


def proposals_for(seq, producer, tool_class, requests):
    """Every proposal whose (producer, class, requests) match,
    in log order: [{proposal_id, queued, released, rejected}].
    Sources: queued decision entries carry the requests; release
    and reject decisions reference the proposal id; executions
    confirm what ran."""
    key = _requests_key(producer, tool_class, requests)
    found = {}
    order = []
    for entry in seq.log.entries:
        body = entry["body"]
        if entry["kind"] != "decision":
            continue
        if body.get("outcome") == "queued" \
                and _requests_key(body.get("producer"),
                                  body.get("class"),
                                  body.get("requests")) == key:
            pid = body["proposal_id"]
            if pid not in found:
                found[pid] = {"proposal_id": pid, "queued": True,
                              "released": False, "rejected": False}
                order.append(pid)
        for flag, field in (("released", "releases"),
                            ("rejected", "rejects")):
            target = body.get(field)
            if target in found:
                found[target][flag] = True
    return [found[pid] for pid in order]


def consumptions(seq, proposal_id):
    """How many times an approval of `proposal_id` has been
    consumed (sense entries published by mark_consumed)."""
    count = 0
    for entry in seq.log.entries:
        body = entry["body"]
        if entry["kind"] == "sense" \
                and body.get("name") == CONSUMED_SENSE \
                and isinstance(body.get("value"), dict) \
                and body["value"].get("proposal_id") == proposal_id:
            count += 1
    return count


def find_unconsumed_release(seq, producer, tool_class, requests):
    """The oldest matching proposal that was released by an
    operator decision and whose approval has not yet been
    consumed, or None. One release authorises one execution."""
    for item in proposals_for(seq, producer, tool_class, requests):
        if item["released"] and not item["rejected"] \
                and consumptions(seq, item["proposal_id"]) == 0:
            return item["proposal_id"]
    return None


def mark_consumed(seq, proposal_id, producer):
    """Record, in the log, that the approval of `proposal_id`
    has now been consumed by one host-side execution."""
    return seq.submit_sense(
        CONSUMED_SENSE,
        {"proposal_id": proposal_id,
         "count": consumptions(seq, proposal_id) + 1},
        producer)
