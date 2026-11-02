"""The learner: standing rules mined from the record (SPEC
section 12).

The pipeline is the standing-rule machine, driven in order:
candidate -> evaluated -> shadow -> canary -> active, with
demotion on regression and one-command revocation. Nothing in
here is trusted because it was learned: a rule's identity is
derived from the instances it was mined from, its effects are
the computed effects of its recogniser definition (none — the
recogniser is pure), and every stage transition is a log entry.

- Mining groups decisions by shape — (producer, class, exact
  effect set) — over a training window; a shape with enough
  support and a dominant outcome becomes a candidate: a pure
  dictionary word that recognises the shape, plus the predicted
  outcome.
- Offline evaluation scores the candidate against the held-out
  tail of the log. Only a pass is deployed to shadow.
- In shadow and canary the rule predicts but never decides; its
  agreement with real outcomes is scored from the log.
- An active rule decides matching proposals through the
  sequencer's rule hook — within constitutional bounds: it never
  overrides a suspension, and it never manufactures a queue.
  Every rule-made decision records what policy would have done,
  so production scoring compares the rule against the
  constitution, not against itself. Sustained disagreement is
  regression: the rule is demoted automatically, in the log.
- Revocation is one call, takes effect on the next proposal,
  and is itself a machine transition in the log.
"""
from .canonical import hash_of
from .envelope import make_envelope
from .primitives import shape_key
from .state import Refusal, rule_stage

_OUTCOME_STORED = {"allow": "allow", "deny": "deny", "queue": "queued"}
_PROTECTED = ("send", "notify", "spend", "irreversible")


def _primary_decisions(entries):
    """The first decision per proposal: release/reject/expire
    follow-ups and fault records are not fresh evidence."""
    for entry in entries:
        if entry["kind"] != "decision":
            continue
        body = entry["body"]
        if body.get("outcome") not in ("allow", "deny", "queued"):
            continue
        if body.get("releases") or body.get("rejects") \
                or body.get("expires") or body.get("fault"):
            continue
        yield entry


def _shape_of(body):
    return (body["producer"], body.get("class", "work"),
            tuple(sorted(body.get("effects", []))))


def _recogniser(candidate):
    shape = candidate["shape"]
    body = ["dup", {"lit": "class"}, "getf", {"lit": shape["class"]},
            "eq", "swap", {"lit": "effects"}, "getf",
            {"lit": list(shape["effects"])}, "eq", "and"]
    return {"name": candidate["definition"],
            "signature": {"ins": ["map"], "outs": ["bool"]},
            "body": body,
            "examples": [
                {"args": [{"class": shape["class"],
                           "effects": list(shape["effects"])}],
                 "expect": [True]},
                {"args": [{"class": shape["class"] + "-other",
                           "effects": list(shape["effects"])}],
                 "expect": [False]}]}


class Learner:
    def __init__(self, min_support=3, dominance_bp=8000,
                 eval_threshold_bp=8000, promote_threshold_bp=9000,
                 stage_min_samples=3, demote_threshold_bp=5000,
                 demote_min_samples=5, train_fraction_bp=7000):
        self.min_support = min_support
        self.dominance_bp = dominance_bp
        self.eval_threshold_bp = eval_threshold_bp
        self.promote_threshold_bp = promote_threshold_bp
        self.stage_min_samples = stage_min_samples
        self.demote_threshold_bp = demote_threshold_bp
        self.demote_min_samples = demote_min_samples
        self.train_fraction_bp = train_fraction_bp

    # -------------------------------------------------- mining
    def mine(self, entries):
        """-> candidate dicts, mined from the training window
        (the first train_fraction of primary decisions). Each
        candidate carries its evidence: support and dominance."""
        decisions = list(_primary_decisions(entries))
        cut = len(decisions) * self.train_fraction_bp // 10000
        train = decisions[:cut] if cut else decisions
        groups = {}
        for entry in train:
            groups.setdefault(_shape_of(entry["body"]), []).append(
                entry["body"]["outcome"])
        candidates = []
        for (producer, cls, effects), outcomes in sorted(groups.items()):
            if len(outcomes) < self.min_support:
                continue
            counts = {}
            for outcome in outcomes:
                counts[outcome] = counts.get(outcome, 0) + 1
            dominant, support = max(counts.items(),
                                    key=lambda kv: (kv[1], kv[0]))
            dominance = 10000 * support // len(outcomes)
            if dominance < self.dominance_bp:
                continue
            shape = {"producer": producer, "class": cls,
                     "effects": list(effects)}
            predicted = {"allow": "allow", "deny": "deny",
                         "queued": "queue"}[dominant]
            digest = hash_of({"shape": shape, "predicted": predicted})[:12]
            candidates.append({
                "rule_id": "rule-" + digest,
                "definition": "candidate-" + digest,
                "shape": shape, "predicted_outcome": predicted,
                "support": len(outcomes), "dominance_bp": dominance,
                "origin": "mined"})
        return candidates

    # -------------------------------------------------- scoring
    def _agreement(self, seq, record, after_seq):
        """Score a rule's prediction against primary decisions
        after a log position. For rule-made decisions the
        comparison is against the recorded policy outcome, never
        against the rule's own decision."""
        samples = 0
        agreed = 0
        shape = record["shape"]
        predicted = _OUTCOME_STORED[record["predicted_outcome"]]
        for entry in _primary_decisions(seq.log.entries):
            if entry["seq"] <= after_seq:
                continue
            body = entry["body"]
            if _shape_of(body) != (shape["producer"], shape["class"],
                                   tuple(shape["effects"])):
                continue
            actual = body.get("policy_outcome", body["outcome"])
            samples += 1
            if actual == predicted:
                agreed += 1
        agreement = 10000 * agreed // samples if samples else None
        return {"samples": samples, "agreed": agreed,
                "agreement_bp": agreement}

    # -------------------------------------------------- records
    def _append_record(self, seq, record):
        seq.log.append("rule", {"producer": "learner", "rule": record})
        seq._refold()

    def _update(self, seq, rule_id, **fields):
        record = dict(seq.state.rules[rule_id])
        record.update(fields)
        self._append_record(seq, record)
        return record

    # -------------------------------------------------- pipeline
    def register(self, seq, candidate):
        """Define the recogniser, register the rule, create its
        standing-rule instance, run offline evaluation on the
        held-out tail, and deploy to shadow on a pass."""
        rule_id = candidate["rule_id"]
        if rule_id in seq.state.rules:
            return {"status": "exists", "rule_id": rule_id}
        verdict = seq.submit(make_envelope(
            "learner", "definition", _recogniser(candidate), [],
            "def-" + rule_id))
        if verdict["status"] != "accepted":
            return {"status": "REFUSED", "rule_id": rule_id,
                    "detail": verdict}
        record = {"rule_id": rule_id,
                  "definition": candidate["definition"],
                  "shape": candidate["shape"],
                  "predicted_outcome": candidate["predicted_outcome"],
                  "support": candidate["support"],
                  "dominance_bp": candidate["dominance_bp"],
                  "origin": candidate.get("origin", "mined")}
        self._append_record(seq, record)
        seq.create_machine_instance("standing-rule", rule_id, "learner")
        decisions = list(_primary_decisions(seq.log.entries))
        cut = len(decisions) * self.train_fraction_bp // 10000
        held_out_after = decisions[cut - 1]["seq"] if 0 < cut <= len(decisions) else -1
        scores = self._agreement(seq, record, held_out_after)
        record = self._update(seq, rule_id, eval=scores)
        passed = scores["samples"] > 0 and scores["agreement_bp"] is not None \
            and scores["agreement_bp"] >= self.eval_threshold_bp
        if not passed:
            return {"status": "eval-failed", "rule_id": rule_id,
                    "eval": scores}
        seq.step_machine(rule_id, "evaluate", {}, "learner")
        seq.step_machine(rule_id, "deploy", {}, "learner")
        self._update(seq, rule_id,
                     shadow_from_seq=seq.log.entries[-1]["seq"])
        return {"status": "shadow", "rule_id": rule_id, "eval": scores}

    def score(self, seq, rule_id):
        record = seq.state.rules[rule_id]
        stage = rule_stage(seq.state, rule_id)
        marker = {"shadow": "shadow_from_seq", "canary": "canary_from_seq",
                  "active": "active_from_seq"}.get(stage)
        after = record.get(marker, -1) if marker else -1
        return {"rule_id": rule_id, "stage": stage,
                **self._agreement(seq, record, after)}

    def promote(self, seq, rule_id):
        """shadow -> canary, on scored evidence."""
        current = self.score(seq, rule_id)
        if current["stage"] != "shadow":
            raise Refusal("FIELD", "rule %s is %s, not shadow"
                          % (rule_id, current["stage"]))
        if current["samples"] < self.stage_min_samples \
                or (current["agreement_bp"] or 0) < self.promote_threshold_bp:
            raise Refusal("CLASS", "rule %s has not earned promotion: %s"
                          % (rule_id, current))
        seq.step_machine(rule_id, "promote", {}, "learner")
        self._update(seq, rule_id,
                     canary_from_seq=seq.log.entries[-1]["seq"])
        return self.score(seq, rule_id)

    def activate(self, seq, rule_id):
        """canary -> active, on scored evidence. Staged: a rule
        whose shape carries protected effects must clear the same
        bar; there is no faster lane for riskier rules."""
        current = self.score(seq, rule_id)
        if current["stage"] != "canary":
            raise Refusal("FIELD", "rule %s is %s, not canary"
                          % (rule_id, current["stage"]))
        if current["samples"] < self.stage_min_samples \
                or (current["agreement_bp"] or 0) < self.promote_threshold_bp:
            raise Refusal("CLASS", "rule %s has not earned activation: %s"
                          % (rule_id, current))
        seq.step_machine(rule_id, "activate", {}, "learner")
        self._update(seq, rule_id,
                     active_from_seq=seq.log.entries[-1]["seq"])
        return self.score(seq, rule_id)

    def check_demotions(self, seq):
        """Production scoring: any active rule whose agreement
        with the constitution has collapsed is demoted, in the
        log, without asking. Returns the demoted rule ids."""
        demoted = []
        for rule_id in sorted(seq.state.rules):
            if rule_stage(seq.state, rule_id) != "active":
                continue
            current = self.score(seq, rule_id)
            if current["samples"] >= self.demote_min_samples \
                    and (current["agreement_bp"] or 0) < self.demote_threshold_bp:
                seq.step_machine(rule_id, "regress", {}, "learner")
                self._update(seq, rule_id, demotion=current)
                demoted.append(rule_id)
        return demoted

    def revoke(self, seq, rule_id):
        """One command, immediate effect, itself a log entry (the
        machine transition). The rule hook reads stage from the
        folded state, so a revoked rule decides nothing further."""
        if rule_id not in seq.state.rules:
            raise Refusal("FIELD", "no such rule: %s" % rule_id)
        if rule_stage(seq.state, rule_id) == "revoked":
            return {"status": "already-revoked", "rule_id": rule_id}
        result = seq.step_machine(rule_id, "revoke", {}, "learner")
        self._update(seq, rule_id, revoked_in_seq=result and
                     seq.log.entries[-1]["seq"])
        return {"status": "revoked", "rule_id": rule_id}

    # -------------------------------------------------- the hook
    def install(self, seq):
        """Wire the rule hook into a sequencer. Only ACTIVE rules
        decide; the hook is consulted per proposal and reads the
        folded state, so stage changes (including revocation and
        demotion) take effect on the next proposal."""
        def decide_by_rule(producer, cls, effects, policy_outcome,
                           policy_reasons):
            if "producer-suspended" in policy_reasons:
                return None  # standing is constitutional; never override
            for rule_id in sorted(seq.state.rules):
                record = seq.state.rules[rule_id]
                if rule_stage(seq.state, rule_id) != "active":
                    continue
                shape = record["shape"]
                if shape["producer"] != producer \
                        or shape["class"] != cls \
                        or tuple(shape["effects"]) != tuple(sorted(effects)):
                    continue
                predicted = record["predicted_outcome"]
                if predicted == "queue":
                    return None  # a rule never manufactures a queue
                return (rule_id, predicted)
            return None

        seq.rule_decider = decide_by_rule
        return seq
