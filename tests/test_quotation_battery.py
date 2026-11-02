"""Slice 17 adversarial battery: the `any`-quotation hazard
(SPEC 0.4, sections 4-5).

Every smuggling route the Phase 4 probe demonstrated or this
slice could construct must end in exactly one of two places:
the verb is ACCOUNTED in the definition's computed effects
(criterion C2, quotation case included), or the definition is
REFUSED(SPEC) at definition time with the form named. There is
no third outcome in which a verb computes effect-free and
emits at evaluation.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "probes"))

from jacquard import Refusal, Sequencer, make_envelope  # noqa: E402
import fold_experiment  # noqa: E402

SNEAKY = {
    "name": "any-write",
    "signature": {"ins": ["list"], "outs": ["bool"]},
    "body": [{"any": ["drop", {"lit": "probe/sneaky"},
                      {"lit": 1}, "write", {"lit": True}]}],
    "examples": [{"args": [[7]], "expect": [True],
                  "requests": ["write"]}]}


def _submit_definition(seq, defn, idem):
    return seq.submit(make_envelope(
        "operator", "definition", defn, [], idem))


def test_original_probe_case_refused_by_name_in_stock_kernel():
    seq = Sequencer()
    verdict = _submit_definition(seq, SNEAKY, "b-original")
    assert verdict["status"] == "REFUSED", verdict
    assert verdict["refusal"] == "SPEC"
    assert "'any'" in verdict["detail"]
    assert "any-write" not in seq.state.dictionary


def test_original_probe_case_accounted_in_the_extension():
    # The quarantined FoldDictionary keeps its form — and now
    # inherits the accounting walk, so the verb it emits is
    # the verb it declares by computation.
    seq = Sequencer()
    fold_experiment.install_fold(seq)
    verdict = _submit_definition(seq, SNEAKY, "b-extension")
    assert verdict["status"] == "accepted", verdict
    assert verdict["computed_effects"] == ["write"]
    stack, requests = seq.evaluate_word("any-write", "operator",
                                        [[1, 2]])
    assert [r["verb"] for r in requests] == ["write", "write"]


def test_nested_quotations_accounted_and_refused():
    defn = {"name": "nested",
            "signature": {"ins": ["list"], "outs": ["bool"]},
            "body": [{"any": [{"any": ["drop", {"lit": "u"},
                                      {"lit": 1}, "write",
                                      {"lit": True}]}]}],
            "examples": []}
    seq = Sequencer()
    # Accounting sees through both levels of nesting.
    assert seq.dictionary.computed_effects(defn) == {"write"}
    verdict = _submit_definition(seq, defn, "b-nested")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"


def test_quotation_inside_an_if_branch():
    defn = {"name": "branchy",
            "signature": {"ins": [], "outs": ["bool"]},
            "body": [{"lit": True},
                     {"if": [{"any": ["drop", {"lit": "u"},
                                      {"lit": 1}, "write",
                                      {"lit": True}]}],
                      "else": [{"lit": False}]}],
            "examples": []}
    seq = Sequencer()
    assert seq.dictionary.computed_effects(defn) == {"write"}
    verdict = _submit_definition(seq, defn, "b-branch")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"


def test_smuggling_via_definition_composition():
    seq = Sequencer()
    # The carrier word is refused, so it never lands...
    verdict = _submit_definition(seq, SNEAKY, "b-carrier")
    assert verdict["status"] == "REFUSED"
    # ...and a word composed on top of it has nothing to
    # reference: refused as an unknown reference, still SPEC.
    wrapper = {"name": "wrapper",
               "signature": {"ins": ["list"], "outs": ["bool"]},
               "body": ["any-write"],
               "examples": []}
    verdict = _submit_definition(seq, wrapper, "b-wrapper")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"
    assert "wrapper" not in seq.state.dictionary


def test_legitimate_composition_still_unions_effects():
    # C2's positive direction, unchanged: a verb inside an if
    # branch of a referenced word is in the caller's union.
    seq = Sequencer()
    inner = {"name": "maybe-write",
             "signature": {"ins": ["bool"], "outs": []},
             "body": [{"if": [{"lit": "u"}, {"lit": 1}, "write"]}],
             "examples": []}
    verdict = _submit_definition(seq, inner, "b-inner")
    assert verdict["status"] == "accepted", verdict
    assert verdict["computed_effects"] == ["write"]
    outer = {"name": "outer",
             "signature": {"ins": ["bool"], "outs": []},
             "body": ["maybe-write"],
             "examples": []}
    verdict = _submit_definition(seq, outer, "b-outer")
    assert verdict["status"] == "accepted", verdict
    assert verdict["computed_effects"] == ["write"]


def test_literal_values_are_data_never_tokens():
    # A literal carrying verb-shaped data is inert: accepted,
    # no computed effects, evaluation emits no requests. This
    # pins the walk's one exclusion — data is not a body, and
    # no form evaluates data as code.
    seq = Sequencer()
    defn = {"name": "data-only",
            "signature": {"ins": [], "outs": ["list"]},
            "body": [{"lit": ["write", "send", {"any": ["spend"]}]}],
            "examples": [{"args": [],
                          "expect": [["write", "send",
                                      {"any": ["spend"]}]]}]}
    verdict = _submit_definition(seq, defn, "b-data")
    assert verdict["status"] == "accepted", verdict
    assert verdict["computed_effects"] == []
    stack, requests = seq.evaluate_word("data-only", "operator", [])
    assert stack == [["write", "send", {"any": ["spend"]}]]
    assert requests == []


def test_hybrid_dict_forms_refused_by_name():
    seq = Sequencer()
    hybrid_if = {"name": "hybrid-if",
                 "signature": {"ins": [], "outs": ["bool"]},
                 "body": [{"lit": True},
                          {"if": [{"lit": True}],
                           "any": [{"lit": True}]}],
                 "examples": []}
    verdict = _submit_definition(seq, hybrid_if, "b-hybrid-if")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"
    hybrid_lit = {"name": "hybrid-lit",
                  "signature": {"ins": [], "outs": ["int"]},
                  "body": [{"lit": 1, "any": []}],
                  "examples": []}
    verdict = _submit_definition(seq, hybrid_lit, "b-hybrid-lit")
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"


def test_forged_body_refused_at_evaluation():
    # A body that never passed define() — forged straight into
    # the evaluator — is refused on the evaluation path too,
    # under the same name.
    seq = Sequencer()
    ctx = seq.context("operator")
    stack, requests = [], []
    with pytest.raises(Refusal) as caught:
        seq.dictionary._exec(
            [{"any": [{"lit": "u"}, {"lit": 1}, "write"]}],
            stack, requests, ctx, {})
    assert caught.value.name == "SPEC"
    assert requests == []
