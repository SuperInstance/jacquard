"""The learner pipeline (SPEC section 12): mining, offline
evaluation, shadow, staged activation, production scoring with
automatic demotion, and one-command revocation. Plus the P9
similarity primitive the learner's evidence rests on.
"""
import pytest

from jacquard import (Learner, Refusal, Sequencer, install_lifecycles,
                      make_envelope, rule_stage)


def kernel():
    seq = Sequencer()
    verdicts = install_lifecycles(seq)
    assert all(v["status"] == "accepted" for v in verdicts.values())
    return seq


def submit_n(seq, producer, cls, verb, args, count, prefix):
    verdicts = []
    for i in range(count):
        body = {"class": cls, "requests": [{"verb": verb, "args": args}]}
        verdicts.append(seq.submit(make_envelope(
            producer, "proposal", body, [verb], "%s-%d" % (prefix, i))))
    return verdicts


def dispatch_history(seq, count=20):
    """The gpu-queue pattern in miniature: one producer, one
    class, one effect, always allowed."""
    return submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
                    [{"job": "j"}], count, "gpu")


def test_mining_finds_the_repeated_shape():
    seq = kernel()
    dispatch_history(seq, 20)
    submit_n(seq, "bob", "report", "write", ["r", 1], 2, "noise")
    candidates = Learner().mine(seq.log.entries)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["shape"] == {"producer": "gpu-daemon",
                                  "class": "gpu-queue",
                                  "effects": ["dispatch"]}
    assert candidate["predicted_outcome"] == "allow"
    assert candidate["support"] >= 3
    assert candidate["dominance_bp"] == 10000


def test_candidate_reaches_shadow_on_gpu_pattern_and_synthetic():
    seq = kernel()
    dispatch_history(seq, 20)
    learner = Learner()
    candidate = learner.mine(seq.log.entries)[0]
    result = learner.register(seq, candidate)
    assert result["status"] == "shadow", result
    assert rule_stage(seq.state, candidate["rule_id"]) == "shadow"
    # the recogniser is a real dictionary word with no effects
    stored = seq.state.dictionary[candidate["definition"]][-1]["definition"]
    assert stored["computed_effects"] == []


def test_shadow_rule_predicts_but_never_decides():
    seq = kernel()
    dispatch_history(seq, 20)
    learner = Learner()
    learner.install(seq)
    candidate = learner.mine(seq.log.entries)[0]
    learner.register(seq, candidate)
    verdict = submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
                       [{"job": "j"}], 1, "after")[0]
    assert verdict["outcome"] == "allow"
    decision = [e for e in seq.log.entries if e["kind"] == "decision"][-1]
    assert "decided_by" not in decision["body"]


def test_full_pipeline_to_active_and_rule_decides():
    seq = kernel()
    dispatch_history(seq, 30)
    learner = Learner()
    learner.install(seq)
    candidate = learner.mine(seq.log.entries)[0]
    rule_id = candidate["rule_id"]
    assert learner.register(seq, candidate)["status"] == "shadow"
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "shadow-window")
    assert learner.promote(seq, rule_id)["stage"] == "canary"
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "canary-window")
    assert learner.activate(seq, rule_id)["stage"] == "active"
    verdict = submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
                       [{"job": "j"}], 1, "governed")[0]
    assert verdict["outcome"] == "allow"
    decision = [e for e in seq.log.entries if e["kind"] == "decision"][-1]
    assert decision["body"]["decided_by"] == rule_id
    assert decision["body"]["policy_outcome"] == "allow"


def test_promotion_requires_evidence():
    seq = kernel()
    dispatch_history(seq, 20)
    learner = Learner()
    candidate = learner.mine(seq.log.entries)[0]
    learner.register(seq, candidate)
    with pytest.raises(Refusal) as caught:
        learner.promote(seq, candidate["rule_id"])
    assert caught.value.name == "CLASS"  # no shadow samples yet


def test_planted_regressing_rule_is_demoted_automatically():
    seq = kernel()
    submit_n(seq, "carol", "work", "write", ["u", 1], 30, "carol")
    learner = Learner()
    learner.install(seq)
    candidate = learner.mine(seq.log.entries)[0]
    rule_id = candidate["rule_id"]
    learner.register(seq, candidate)
    submit_n(seq, "carol", "work", "write", ["u", 1], 4, "s-win")
    learner.promote(seq, rule_id)
    submit_n(seq, "carol", "work", "write", ["u", 1], 4, "c-win")
    learner.activate(seq, rule_id)
    assert rule_stage(seq.state, rule_id) == "active"
    # The plant: carol is suspended. Policy now denies everything
    # she sends; the rule still predicts allow. Reality has moved.
    seq.set_standing("carol", {"status": "suspended"})
    submit_n(seq, "carol", "work", "write", ["u", 1], 6, "regress")
    demoted = learner.check_demotions(seq)
    assert demoted == [rule_id]
    assert rule_stage(seq.state, rule_id) == "demoted"
    transitions = [e["body"] for e in seq.log.entries
                   if e["kind"] == "transition"
                   and e["body"]["instance"] == rule_id
                   and e["body"]["event"] == "regress"]
    assert transitions and transitions[-1]["outcome"] == "taken"
    record = seq.state.rules[rule_id]
    assert record["demotion"]["agreement_bp"] == 0


def test_revocation_is_immediate_and_logged():
    seq = kernel()
    dispatch_history(seq, 30)
    learner = Learner()
    learner.install(seq)
    candidate = learner.mine(seq.log.entries)[0]
    rule_id = candidate["rule_id"]
    learner.register(seq, candidate)
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "s2")
    learner.promote(seq, rule_id)
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "c2")
    learner.activate(seq, rule_id)
    assert learner.revoke(seq, rule_id)["status"] == "revoked"
    assert rule_stage(seq.state, rule_id) == "revoked"
    verdict = submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
                       [{"job": "j"}], 1, "post-revoke")[0]
    assert verdict["outcome"] == "allow"
    decision = [e for e in seq.log.entries if e["kind"] == "decision"][-1]
    assert "decided_by" not in decision["body"]


def test_eval_failure_keeps_the_candidate_at_candidate():
    seq = kernel()
    # Train on allows, then flip: the held-out tail is all denies
    # (the producer gets suspended before the tail is submitted).
    submit_n(seq, "dave", "work", "write", ["u", 1], 14, "train")
    seq.set_standing("dave", {"status": "suspended"})
    submit_n(seq, "dave", "work", "write", ["u", 1], 6, "tail")
    learner = Learner()
    candidates = learner.mine(seq.log.entries)
    assert candidates and candidates[0]["predicted_outcome"] == "allow"
    result = learner.register(seq, candidates[0])
    assert result["status"] == "eval-failed"
    assert rule_stage(seq.state, candidates[0]["rule_id"]) == "candidate"


# ---------------------------------------------------------- P9

def test_similar_reads_the_actors_own_history():
    seq = kernel()
    dispatch_history(seq, 5)
    submit_n(seq, "bob", "gpu-queue", "dispatch", [{"job": "x"}], 3, "bob")
    seq.submit(make_envelope("operator", "definition", {
        "name": "recent-similar",
        "signature": {"ins": ["str", "int"], "outs": ["list"]},
        "body": ["similar"],
        "examples": []}, [], "def-sim"))
    stack, _requests = seq.evaluate_word(
        "recent-similar", "gpu-daemon", ["gpu-queue|dispatch", 10])
    matches = stack[0]
    assert len(matches) == 5  # only gpu-daemon's own, not bob's
    assert all(m["outcome"] == "allow" for m in matches)
    stack, _ = seq.evaluate_word("recent-similar", "gpu-daemon",
                                 ["gpu-queue|dispatch", 2])
    assert len(stack[0]) == 2
