"""The machine profile: parser, static checker, runtime.

Each named refusal has a deliberately broken machine. The seven
lifecycle machines must pass the checker as shipped.
"""
import pytest

from jacquard import (LIFECYCLES, Refusal, Sequencer, check_machine,
                      install_lifecycles, make_envelope, parse_machine)


def no_words(name):
    return None


def submit_machine(seq, text, ident="m1"):
    return seq.submit(make_envelope("operator", "machine",
                                    {"text": text}, [], ident))


# ---------------------------------------------------------- parser

def test_parse_minimal_machine():
    parsed = parse_machine(LIFECYCLES["commit-batch"])
    assert parsed["name"] == "commit-batch"
    assert parsed["initial"] == "open"
    assert parsed["terminals"] == ["folded", "aborted"]
    assert set(parsed["states"]) == {"open", "sealed", "folded", "aborted"}
    assert len(parsed["transitions"]) == 4


def test_parse_rejects_garbage():
    with pytest.raises(Refusal) as caught:
        parse_machine("this is not a machine")
    assert caught.value.name == "FIELD"


def test_all_lifecycles_pass_the_checker():
    for name, text in LIFECYCLES.items():
        parsed = parse_machine(text)
        assert check_machine(parsed, no_words)["name"] == name


# ------------------------------------------------- named refusals

UNREACHABLE_MACHINE = """\
machine limbo-test
initial: a
terminal: b
events: go
a -> b : go
b -> b : go
state limbo
limbo -> limbo : go
ignore go in *
"""

DEAD_MACHINE = """\
machine stuck-test
initial: a
terminal: b
events: go, detour
a -> b : go
a -> stuck : detour
b -> b : go
stuck -> stuck : detour
ignore go in *
ignore detour in *
"""

AMBIGUOUS_MACHINE = """\
machine fork-test
initial: a
terminal: b
events: go
a -> b : go
a -> b : go [first-guard]
ignore go in *
"""

NONTOTAL_MACHINE = """\
machine gap-test
initial: a
terminal: b
events: go, wait
a -> b : go
b -> b : go
"""


def test_unreachable_refused_by_name():
    seq = Sequencer()
    verdict = submit_machine(seq, UNREACHABLE_MACHINE)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNREACHABLE"
    assert "limbo" in verdict["detail"]


def test_dead_refused_by_name():
    seq = Sequencer()
    verdict = submit_machine(seq, DEAD_MACHINE)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "DEAD"
    assert "stuck" in verdict["detail"]


def test_ambiguous_refused_by_name():
    seq = Sequencer()
    seq.submit(make_envelope("operator", "definition", {
        "name": "first-guard",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["drop", {"lit": True}],
        "examples": [{"args": [{}], "expect": [True]}]}, [], "d-guard"))
    verdict = submit_machine(seq, AMBIGUOUS_MACHINE)
    # a plain transition competing with a guarded one on (a, go)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "AMBIGUOUS"


def test_nontotal_refused_by_name():
    seq = Sequencer()
    verdict = submit_machine(seq, NONTOTAL_MACHINE)
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "NON_TOTAL"
    assert "wait" in verdict["detail"]


def test_unknown_guard_word_is_a_spec_refusal():
    seq = Sequencer()
    text = ("machine g\ninitial: a\nterminal: b\nevents: go\n"
            "a -> b : go [no-such-word]\nignore go in *\n")
    verdict = submit_machine(seq, text)
    assert verdict["refusal"] == "SPEC"


def test_guard_with_wrong_signature_is_a_field_refusal():
    seq = Sequencer()
    seq.submit(make_envelope("operator", "definition", {
        "name": "not-a-guard",
        "signature": {"ins": ["int"], "outs": ["int"]},
        "body": ["dup", "add"],
        "examples": [{"args": [2], "expect": [4]}]}, [], "d-ng"))
    text = ("machine g2\ninitial: a\nterminal: b\nevents: go\n"
            "a -> b : go [not-a-guard]\nignore go in *\n")
    verdict = submit_machine(seq, text)
    assert verdict["refusal"] == "FIELD"


def test_guard_with_effects_is_a_spec_refusal():
    seq = Sequencer()
    seq.submit(make_envelope("operator", "definition", {
        "name": "loud-guard",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["drop", {"lit": "unit/x"}, {"lit": 1}, "write",
                 {"lit": True}],
        "examples": [{"args": [{}], "expect": [True],
                      "requests": ["write"]}]}, [], "d-lg"))
    text = ("machine g3\ninitial: a\nterminal: b\nevents: go\n"
            "a -> b : go [loud-guard]\nignore go in *\n")
    verdict = submit_machine(seq, text)
    assert verdict["refusal"] == "SPEC"
    assert "pure" in verdict["detail"]


# ---------------------------------------------------------- runtime

GUARDED_MACHINE = """\
machine intake
initial: open
terminal: filed, bounced
events: file, bounce
open -> filed : file [is-complete] / mark-filed
open -> bounced : file otherwise
open -> bounced : bounce
ignore file in *
ignore bounce in *
"""


def guarded_kernel():
    seq = Sequencer()
    seq.submit(make_envelope("operator", "definition", {
        "name": "is-complete",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": [{"lit": "complete"}, "getf"],
        "examples": [{"args": [{"complete": True}], "expect": [True]},
                     {"args": [{"complete": False}], "expect": [False]}]},
        [], "d-ic"))
    seq.submit(make_envelope("operator", "definition", {
        "name": "mark-filed",
        "signature": {"ins": ["map"], "outs": []},
        "body": ["drop", {"lit": "intake/filed"}, {"lit": True}, "write"],
        "examples": [{"args": [{}], "expect": [],
                      "requests": ["write"]}]}, ["write"], "d-mf"))
    verdict = submit_machine(seq, GUARDED_MACHINE, "m-intake")
    assert verdict["status"] == "accepted", verdict
    return seq


def test_guard_true_takes_guarded_transition_and_runs_action():
    seq = guarded_kernel()
    seq.create_machine_instance("intake", "doc-1")
    result = seq.step_machine("doc-1", "file", {"complete": True})
    assert result["status"] == "taken"
    assert result["to"] == "filed"
    assert [r["verb"] for r in result["requests"]] == ["write"]
    assert seq.machine_instance_state("doc-1") == "filed"


def test_guard_false_falls_to_otherwise():
    seq = guarded_kernel()
    seq.create_machine_instance("intake", "doc-2")
    result = seq.step_machine("doc-2", "file", {"complete": False})
    assert result["status"] == "taken"
    assert result["to"] == "bounced"
    assert result["requests"] == []


def test_ignored_event_is_logged_and_changes_nothing():
    seq = guarded_kernel()
    seq.create_machine_instance("intake", "doc-3")
    seq.step_machine("doc-3", "file", {"complete": True})
    before = len(seq.log.entries)
    result = seq.step_machine("doc-3", "bounce")
    assert result["status"] == "ignored"
    assert seq.machine_instance_state("doc-3") == "filed"
    assert len(seq.log.entries) == before + 1
    entry = seq.log.entries[-1]
    assert entry["kind"] == "transition"
    assert entry["body"]["outcome"] == "ignored"


def test_every_step_is_in_the_log():
    seq = guarded_kernel()
    seq.create_machine_instance("intake", "doc-4")
    seq.step_machine("doc-4", "file", {"complete": False})
    kinds = [(e["kind"], e["body"].get("outcome"))
             for e in seq.log.entries if e["kind"] == "transition"]
    assert kinds == [("transition", "created"), ("transition", "taken")]


def test_stepping_unknown_instance_refused():
    seq = Sequencer()
    with pytest.raises(Refusal) as caught:
        seq.step_machine("nope", "go")
    assert caught.value.name == "FIELD"
