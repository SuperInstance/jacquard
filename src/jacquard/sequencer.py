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
  operator releases, rejects or expires them; deciding never
  stalls other work;
- machine envelopes are parsed and checked by the machine
  profile; accepted machines are appended, and any kernel with
  the lifecycle machines installed runs its proposal, action,
  approval and standing lifecycles through them, writing a
  transition entry for every step.

Submitting the same envelope twice returns the original verdict
and appends nothing (idempotency by envelope id).
"""
import copy

from .dictionary import Dictionary
from .envelope import envelope_hash, validate_envelope
from .log import Log
from .machines import check_machine, find_transition, parse_machine
from .policy import POLICY_VERSION, decide
from .primitives import TIER_E, EvalContext
from .records import records as project_records
from .scheduler import Scheduler
from .state import Refusal, fold


class Sequencer:
    def __init__(self, log=None, standing=None):
        self.log = log if log is not None else Log()
        self.standing = standing if standing is not None else {}
        self.tentative = {}
        self._verdicts = {}
        self.admission = Scheduler()
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

    # --------------------------------------- budgets and prices
    def grant_budget(self, producer, amount, by="operator"):
        """Grant accounting units to a producer. A log entry: the
        folded balance is grants minus priced spends."""
        entry = self.log.append("budget", {
            "producer": producer, "delta": int(amount), "by": by})
        self._refold()
        return {"entry": entry["hash"],
                "balance": self.state.budgets.get(producer, 0)}

    def post_price(self, resource, price, by="operator"):
        """Post the price of a resource in the accounting unit.
        Prices are versioned by the log: a spend is charged at the
        price posted at its point in the log."""
        entry = self.log.append("price", {
            "resource": resource, "price": int(price), "by": by})
        self._refold()
        return {"entry": entry["hash"], "price": int(price)}

    def buy_weight(self, producer, cls, extra, resource="compute"):
        """Purchase extra scheduling weight for a flow from the
        producer's budget, at the posted price of `resource` per
        unit of extra weight. The purchase is a budget entry (the
        evidence) plus a scheduler record (the mechanism); the
        extra weight decays to baseline with virtual time.
        Insufficient budget is a CONSERVATION refusal: budgets
        degrade, they never borrow."""
        extra = int(extra)
        price = self.state.prices.get(resource, 1)
        cost = extra * price
        balance = self.state.budgets.get(producer, 0)
        if cost > balance:
            raise Refusal("CONSERVATION",
                          "weight purchase costs %d, budget is %d"
                          % (cost, balance))
        self.log.append("budget", {
            "producer": producer, "delta": -cost,
            "reason": "weight-purchase", "flow": [producer, cls],
            "extra": extra, "resource": resource})
        self.admission.purchase((producer, cls), extra)
        self._refold()
        return {"cost": cost,
                "balance": self.state.budgets.get(producer, 0),
                "weight": self.admission.weight((producer, cls))}

    # --------------------------------------- batch admission
    def submit_batch(self, envelopes):
        """Admit a batch of proposals through the WFQ admission
        scheduler: every proposal is queued under its flow, then
        served in fair order and submitted through the normal
        path. Non-proposal envelopes bypass the scheduler in
        arrival order. Returns verdicts in served order."""
        verdicts = []
        queued = []
        for envelope in envelopes:
            if envelope.get("kind") == "proposal":
                flow = (envelope["producer"],
                        envelope["body"].get("class", "work"))
                self.admission.submit(flow, envelope)
                queued.append(envelope)
            else:
                verdicts.append(self.submit(envelope))
        while True:
            envelope = self.admission.serve_next()
            if envelope is None:
                break
            verdicts.append(self.submit(envelope))
        return verdicts

    def decision_order(self):
        """The decision queue in WFQ presentation order: flows by
        their current (possibly purchased) weights, items in
        queueing order within the rule of the finish tags."""
        items = []
        for proposal_id, body in self.state.decision_queue.items():
            flow = (body["producer"], body.get("class", "work"))
            items.append((flow, proposal_id, 1))
        return self.admission.order(items)

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
        elif envelope["kind"] == "machine":
            verdict = self._submit_machine(envelope)
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

    # -------------------------------------------------- machines
    def _machine_definition(self, name):
        versions = self.state.machines.get(name)
        if not versions:
            return None
        return versions[-1]["definition"]

    def machine_instance_state(self, instance):
        current = self.state.machine_instances.get(instance)
        return current["state"] if current else None

    def _resolve_word(self, name):
        resolved = self.dictionary._resolve(name)
        if resolved is None or resolved[0] != "word":
            return None
        _kind, ins, outs, _entry_hash, definition = resolved
        return (ins, outs, set(definition["computed_effects"]))

    def _submit_machine(self, envelope):
        body = envelope["body"]
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            return {"status": "REFUSED", "refusal": "FIELD",
                    "detail": "machine body must be {\"text\": <text>}"}
        try:
            parsed = parse_machine(body["text"])
            stored = check_machine(parsed, self._resolve_word)
        except Refusal as refusal:
            return {"status": "REFUSED", "refusal": refusal.name,
                    "detail": refusal.detail}
        stored = dict(stored)
        effects = set()
        for transition in stored["transitions"]:
            if transition["action"]:
                versions = self.state.dictionary[transition["action"]]
                effects |= set(versions[-1]["definition"]["computed_effects"])
        stored["action_effects"] = sorted(effects)
        entry = self.log.append("machine", {
            "producer": envelope["producer"], "machine": stored})
        self._refold()
        return {"status": "accepted", "entry": entry["hash"],
                "machine": stored["name"]}

    def create_machine_instance(self, machine, instance, producer="operator"):
        definition = self._machine_definition(machine)
        if definition is None:
            raise Refusal("SPEC", "no such machine: %s" % machine)
        if instance in self.state.machine_instances:
            raise Refusal("FIELD", "instance already exists: %s" % instance)
        entry = self.log.append("transition", {
            "producer": producer, "machine": machine, "instance": instance,
            "event": "@create", "from": None, "to": definition["initial"],
            "outcome": "created"})
        self._refold()
        return entry

    def step_machine(self, instance, event, payload=None, producer="operator"):
        """Fire one event at a machine instance. The transition
        hook writes every step to the log — taken, ignored, or
        guard-blocked — before the result is reported."""
        current = self.state.machine_instances.get(instance)
        if current is None:
            raise Refusal("FIELD", "no such machine instance: %s" % instance)
        definition = self._machine_definition(current["machine"])
        candidates, ignored = find_transition(definition, current["state"],
                                              event)
        payload = payload if isinstance(payload, dict) else {}
        ctx = self.context(producer)
        chosen = None
        for candidate in candidates:
            if candidate["guard"]:
                stack, emitted = self.dictionary.evaluate(
                    candidate["guard"], [payload], ctx)
                if emitted:
                    raise Refusal("SPEC", "guard %s emitted requests"
                                  % candidate["guard"])
                if stack == [True]:
                    chosen = candidate
                    break
                if stack != [False]:
                    raise Refusal("FIELD", "guard %s must leave exactly "
                                  "one bool" % candidate["guard"])
            elif not candidate["otherwise"]:
                chosen = candidate
                break
        if chosen is None:
            for candidate in candidates:
                if candidate["otherwise"]:
                    chosen = candidate
                    break
        if chosen is not None:
            requests = []
            if chosen["action"]:
                _stack, requests = self.dictionary.evaluate(
                    chosen["action"], [payload], ctx)
            self.log.append("transition", {
                "producer": producer, "machine": current["machine"],
                "instance": instance, "event": event,
                "from": current["state"], "to": chosen["to"],
                "guard": chosen["guard"], "action": chosen["action"],
                "requests": requests, "outcome": "taken"})
            self._refold()
            return {"status": "taken", "instance": instance, "event": event,
                    "from": current["state"], "to": chosen["to"],
                    "requests": requests}
        outcome = "ignored" if ignored else "no-transition"
        self.log.append("transition", {
            "producer": producer, "machine": current["machine"],
            "instance": instance, "event": event,
            "from": current["state"], "to": current["state"],
            "guard": None, "action": None, "requests": [],
            "outcome": outcome})
        self._refold()
        return {"status": outcome, "instance": instance, "event": event,
                "from": current["state"], "to": current["state"],
                "requests": []}

    def _lifecycle(self, machine, instance, event, producer, payload=None):
        """Step a lifecycle instance if its machine is installed
        in this kernel; otherwise do nothing. Returns the step
        result or None."""
        definition = self._machine_definition(machine)
        if definition is None:
            return None
        if instance not in self.state.machine_instances:
            self.create_machine_instance(machine, instance, producer)
        return self.step_machine(instance, event, payload, producer)

    def report_action(self, action_id, event, producer="operator",
                      payload=None):
        """Report an executor outcome for a dispatched action:
        confirm, fail, compensate (or reject before dispatch)."""
        return self.step_machine(action_id, event, payload, producer)

    def transition_standing(self, producer, event):
        """Move a producer's standing through the producer-standing
        machine and mirror the result into the policy gate's view."""
        instance = "producer:" + producer
        if self._machine_definition("producer-standing") is None:
            raise Refusal("SPEC", "producer-standing machine not installed")
        if instance not in self.state.machine_instances:
            self.create_machine_instance("producer-standing", instance)
        result = self.step_machine(instance, event, {}, "operator")
        self.standing[producer] = {"status": result["to"]}
        return result

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
        self._lifecycle("proposal", env_hash, "submit", producer)
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
            self._lifecycle("proposal", env_hash, "refuse", producer)
            return {"status": "REFUSED", "refusal": "UNDERDECLARED",
                    "detail": detail, "proposal_id": env_hash}
        # Definitions inside a proposal are checked against the
        # committed dictionary before anything is appended, so a
        # proposal applies atomically or not at all.
        for request in requests:
            if request["verb"] == "define":
                try:
                    self.dictionary.define(request["args"][0])
                except Refusal as refusal:
                    self._lifecycle("proposal", env_hash, "refuse", producer)
                    return {"status": "REFUSED", "refusal": refusal.name,
                            "detail": refusal.detail,
                            "proposal_id": env_hash}
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
            self._lifecycle("proposal", env_hash, "decide", producer)
            self._execute(producer, cls, env_hash, body)
            self._lifecycle("proposal", env_hash, "commit", producer)
            self._lifecycle("proposal", env_hash, "close", producer)
        elif outcome == "deny":
            self._lifecycle("proposal", env_hash, "refuse", producer)
        elif outcome == "queue":
            self._lifecycle("proposal", env_hash, "hold", producer)
            if self._machine_definition("approval") is not None:
                self.create_machine_instance(
                    "approval", "approval:" + env_hash, producer)
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
        for index, (request, stored) in enumerate(zip(requests, prepared)):
            if request["verb"] == "define":
                self.log.append("definition", {
                    "producer": producer, "definition": stored})
            else:
                item = {"verb": request["verb"], "args": request["args"]}
                for extra in ("outputs",):
                    if extra in request:
                        item[extra] = request[extra]
                applied.append(item)
                if request["verb"] == "dispatch":
                    payload = request["args"][0] \
                        if request["args"] and isinstance(request["args"][0], dict) else {}
                    action_id = "%s/action-%d" % (proposal_id, index)
                    self._lifecycle("action", action_id, "approve",
                                    producer, payload)
                    if action_id in self.state.machine_instances:
                        self.step_machine(action_id, "dispatch",
                                          payload, producer)
        self.log.append("execution", {
            "producer": producer, "class": cls, "proposal_id": proposal_id,
            "applied": applied, "uses": body.get("uses", [])})
        self._refold()

    def _approval_step(self, proposal_id, event, producer):
        instance = "approval:" + proposal_id
        if instance not in self.state.machine_instances:
            return
        if self.machine_instance_state(instance) == "pending" \
                and event in ("approve", "deny"):
            self.step_machine(instance, "present", {}, producer)
        self.step_machine(instance, event, {}, producer)

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
        self._approval_step(proposal_id, "approve", operator)
        self._lifecycle("proposal", proposal_id, "decide", producer)
        body = {"requests": queued.get("requests", []),
                "uses": queued.get("uses", [])}
        self._execute(producer, cls, proposal_id, body)
        self._lifecycle("proposal", proposal_id, "commit", producer)
        self._lifecycle("proposal", proposal_id, "close", producer)
        self._refold()
        return {"status": "decided", "outcome": "allow",
                "released": proposal_id}

    def reject_queued(self, proposal_id, operator):
        queued = self.state.decision_queue.get(proposal_id)
        if queued is None:
            return {"status": "REFUSED", "refusal": "FIELD",
                    "detail": "no queued proposal with id %s" % proposal_id}
        producer = queued["producer"]
        cls = queued.get("class", "work")
        self.log.append("decision", {
            "producer": producer, "class": cls, "proposal_id": proposal_id,
            "policy_version": POLICY_VERSION, "outcome": "deny",
            "reasons": ["rejected-by-operator"], "rejects": proposal_id,
            "rejected_by": operator, "effects": queued.get("effects", [])})
        self._approval_step(proposal_id, "deny", operator)
        self._lifecycle("proposal", proposal_id, "refuse", producer)
        self._refold()
        return {"status": "decided", "outcome": "deny",
                "rejected": proposal_id}

    def expire_queued(self, proposal_id, operator):
        queued = self.state.decision_queue.get(proposal_id)
        if queued is None:
            return {"status": "REFUSED", "refusal": "FIELD",
                    "detail": "no queued proposal with id %s" % proposal_id}
        producer = queued["producer"]
        cls = queued.get("class", "work")
        self.log.append("decision", {
            "producer": producer, "class": cls, "proposal_id": proposal_id,
            "policy_version": POLICY_VERSION, "outcome": "expired",
            "reasons": ["expired-in-queue"], "expires": proposal_id,
            "expired_by": operator, "effects": queued.get("effects", [])})
        self._approval_step(proposal_id, "expire", operator)
        self._lifecycle("proposal", proposal_id, "refuse", producer)
        self._refold()
        return {"status": "decided", "outcome": "expired",
                "expired": proposal_id}
