import pytest

from jacquard import Sequencer, make_envelope
from jacquard.state import Refusal


def define(seq, defn, declared=None, idem="d"):
    return seq.submit(make_envelope(
        "operator", "definition", defn,
        declared if declared is not None
        else defn.get("declared_effects", []), idem))


def base(defn):
    return {"name": "base", "signature": {"ins": ["int"], "outs": ["int"]},
            "body": [{"lit": 10}, "add"],
            "examples": [{"args": [0], "expect": [10]}]}


def test_signature_mismatch_refused():
    seq = Sequencer()
    bad = {"name": "w", "signature": {"ins": ["int"], "outs": ["bool"]},
           "body": ["dup", "add"],
           "examples": [{"args": [1], "expect": [2]}]}
    with pytest.raises(Refusal) as caught:
        seq.dictionary.define(bad)
    assert caught.value.name == "FIELD"


def test_example_mismatch_refused_by_name():
    seq = Sequencer()
    bad = {"name": "w", "signature": {"ins": ["int"], "outs": ["int"]},
           "body": ["dup", "add"],
           "examples": [{"args": [3], "expect": [7]}]}
    verdict = define(seq, bad)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "EXAMPLE"


def test_underdeclared_definition_refused():
    seq = Sequencer()
    dishonest = {"name": "sneaky",
                 "signature": {"ins": ["map"], "outs": []},
                 "body": ["dispatch"], "declared_effects": ["reads"],
                 "examples": [{"args": [{"job": "j"}],
                               "requests": ["dispatch"]}]}
    verdict = define(seq, dishonest, declared=["reads"])
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"


def test_unknown_reference_refused():
    seq = Sequencer()
    bad = {"name": "w", "signature": {"ins": [], "outs": []},
           "body": ["no-such-word"], "examples": [{"args": [], "expect": []}]}
    verdict = define(seq, bad)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "SPEC"


def test_if_branch_shape_mismatch_refused():
    seq = Sequencer()
    bad = {"name": "w", "signature": {"ins": ["bool"], "outs": ["int"]},
           "body": [{"if": [{"lit": 1}], "else": []}],
           "examples": [{"args": [True], "expect": [1]}]}
    with pytest.raises(Refusal):
        seq.dictionary.define(bad)


def test_refs_pinning_redefinition_does_not_change_callers():
    seq = Sequencer()
    assert define(seq, base(base), idem="d1")["status"] == "accepted"
    user = {"name": "use-base",
            "signature": {"ins": ["int"], "outs": ["int"]},
            "body": ["base", "base"],
            "examples": [{"args": [0], "expect": [20]}]}
    assert define(seq, user, idem="d2")["status"] == "accepted"
    v2 = {"name": "base", "signature": {"ins": ["int"], "outs": ["int"]},
          "body": [{"lit": 100}, "add"],
          "examples": [{"args": [0], "expect": [100]}]}
    assert define(seq, v2, idem="d3")["status"] == "accepted"
    # The caller still runs the version it was defined against.
    stack, _ = seq.evaluate_word("use-base", "operator", [0])
    assert stack == [20]
    # A direct call uses the latest version.
    stack, _ = seq.evaluate_word("base", "operator", [0])
    assert stack == [100]
