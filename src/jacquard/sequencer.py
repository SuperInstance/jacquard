"""The sequencer (SPEC sections 3 and 7).

One writer. Every envelope passes here, in order, and every
outcome is written to the log before it is reported:

- malformed envelopes and seal mismatches are refused without
  touching the log;
- definition envelopes are checked by the dictionary; accepted
  definitions are appended, refusals are returned by name;
- proposal envelopes are checked for effect coverage, decided by
  the policy gate, and — when allowed — executed atomically:
  either every request applies or none does;
- proposals the gate queues wait in the decision queue until the
  operator releases them; deciding never stalls other work.

Submitting the same envelope twice returns the original verdict
and appends nothing (idempotency by envelope id).
"""
import copy

from .dictionary import Dictionary
from .envelope import envelope_hash, validate_envelope
from .log import Log
from .policy import POLICY_VERSION, decide
from .primitives import TIER_E, EvalContext
from .records import records as project_records
from .state import Refusal, fold


class Sequencer:
    def __init__(self, log=None, standing=None):
        self.log = log if log is not None else Log()
        self.standing = standing if standing is not None else {}
        self.tentative = {}
        self._verdicts = {}
        self.state = fold(self.log.entries)
        self.dictionary = Dictionary(
            self.state, lambda: self.log.entries,
            lambda: self.tentative, self._record_lookup)

    # -------------------------------------------------- plumbing
    def _refold(self):
        self.state = fold(self.log.entries)
        self.dictionary.state = self.state

    def _record_lookup(self, producer, cls):
        view = project_records(self.log.entries)
        return view.get(producer, {}).get(cls, {})

    def context(self, producer):
        return EvalContext(self.state, self.log.entries, producer,
                           self.tentative, self._record_lookup)

    def evaluate_word(self, name, producer, args=None):
        """Evaluate a definition against current state. Appends
        nothing to the log; returns (stack, requests)."""
        return self.dictionary.evaluate(
            name, list(args) if args else [], self.context(producer))

    def set_standing(self, producer, standing):
        self.standing[producer] = standing

    # -------------------------------------------------- senses
    def submit_sense(self, name, value, producer):
        entry = self.log.append("sense", {"producer": producer,
                                          "name": name, "value": value})
        self._refold()
        return entry

    def checkpoint(self, name):
        entry = self.log.append("checkpoint", {
            "name": name, "state_hash": self.state.state_hash()})
        self._refold()
        return entry

    # -------------------------------------------------- submit
    def submit(self, envelope):
        problem = validate_envelope(envelope)
        if problem is not None:
            return {"status": "REFUSED", "refusal": problem[0],
                    "detail": problem[1]}
        env_hash = envelope_hash(envelope)
        if env_hash in self._verdicts:
            return copy.deepcopy(self._verdicts[env_hash])
        if envelope["kind"] == "definition":
            verdict = self._submit_definition(envelope)
        else:
            verdict = self._submit_proposal(envelope, env_hash)
        self._verdicts[env_hash] = copy.deepcopy(verdict)
        return verdict

    def _submit_definition(self, envelope):
        try:
            stored = self.dictionary.define(envelope["body"])
        except Refusal as refusal:
            return {"status": "REFUSED", "refusal": refusal.name,
                    "detail": refusal.detail}
        entry = self.log.append("definition", {
            "producer": envelope["producer"], "definition": stored})
        self._refold()
        return {"status": "accepted", "entry": entry["hash"],
                "computed_effects": stored["computed_effects"]}

    def _check_requests(self, requests):
        if not isinstance(requests, list):
            return ("FIELD", "proposal body.requests must be a list")
        for request in requests:
            if not isinstance(request, dict) or "verb" not in request \
                    or "args" not in request:
                return ("FIELD", "each request needs verb and args")
            if request["verb"] not in TIER_E:
                return ("FIELD", "unknown effect verb: %r" % (request["verb"],))
            if request["verb"] == "write":
                args = request["args"]
                if len(args) != 2 or not isinstance(args[0], str):
                    return ("FIELD", "write expects [unit, value]")
        return None

    def _submit_proposal(self, envelope, env_hash):
        producer = envelope["producer"]
        body = envelope["body"]
        cls = body.get("class", "work")
        requests = body.get("requests")
        problem = self._check_requests(requests)
        if problem is not None:
            return {"status": "REFUSED", "refusal": problem[0],
                    "detail": problem[1]}
        effects = set()
        for request in requests:
            effects.add(request["verb"])
        if body.get("irreversible"):
            effects.add("irreversible")
        declared = set(envelope["declared_effects"])
        if not effects <= declared:
            detail = ("declared effects %s do not cover actual effects %s"
                      % (sorted(declared), sorted(effects)))
            self.log.append("decision", {
                "producer": producer, "class": cls, "proposal_id": env_hash,
                "policy_version": POLICY_VERSION, "outcome": "refused",
                "fault": "UNDERDECLARED", "reasons": [detail],
                "effects": sorted(effects)})
            self._refold()
            return {"status": "REFUSED", "refusal": "UNDERDECLARED",
                    "detail": detail, "proposal_id": env_hash}
        view = self._record_lookup(producer, cls)
        outcome, reasons = decide(producer, envelope["kind"], effects,
                                  view, self.standing.get(producer))
        decision = {"producer": producer, "class": cls,
                    "proposal_id": env_hash,
                    "policy_version": POLICY_VERSION,
                    "outcome": {"allow": "allow", "deny": "deny",
                                "queue": "queued"}[outcome],
                    "reasons": reasons, "effects": sorted(effects)}
        if outcome == "queue":
            decision["requests"] = requests
            decision["irreversible"] = bool(body.get("irreversible"))
            decision["uses"] = body.get("uses", [])
        self.log.append("decision", decision)
        if outcome == "allow":
            self._execute(producer, cls, env_hash, body)
        self._refold()
        return {"status": "decided", "outcome": outcome,
                "proposal_id": env_hash, "reasons": reasons}

    # -------------------------------------------------- execution
    def _execute(self, producer, cls, proposal_id, body):
        requests = body.get("requests", [])
        # Pre-validate definitions so a proposal applies atomically.
        prepared = []
        for request in requests:
            if request["verb"] == "define":
                prepared.append(self.dictionary.define(request["args"][0]))
            else:
                prepared.append(None)
        applied = []
        for request, stored in zip(requests, prepared):
            if request["verb"] == "define":
                self.log.append("definition", {
                    "producer": producer, "definition": stored})
            else:
                item = {"verb": request["verb"], "args": request["args"]}
                for extra in ("outputs",):
                    if extra in request:
                        item[extra] = request[extra]
                applied.append(item)
        self.log.append("execution", {
            "producer": producer, "class": cls, "proposal_id": proposal_id,
            "applied": applied, "uses": body.get("uses", [])})
        self._refold()

    def release_queued(self, proposal_id, operator):
        queued = self.state.decision_queue.get(proposal_id)
        if queued is None:
            return {"status": "REFUSED", "refusal": "FIELD",
                    "detail": "no queued proposal with id %s" % proposal_id}
        producer = queued["producer"]
        cls = queued.get("class", "work")
        self.log.append("decision", {
            "producer": producer, "class": cls, "proposal_id": proposal_id,
            "policy_version": POLICY_VERSION, "outcome": "allow",
            "reasons": ["released-by-operator"], "releases": proposal_id,
            "released_by": operator, "effects": queued.get("effects", [])})
        body = {"requests": queued.get("requests", []),
                "uses": queued.get("uses", [])}
        self._execute(producer, cls, proposal_id, body)
        self._refold()
        return {"status": "decided", "outcome": "allow",
                "released": proposal_id}
