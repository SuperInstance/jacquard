"""Acceptance criterion 2 (design doc 10, section 5).

Tier-E verbs inside a definition produce requests, never
executions, and a definition's effects are computed from its
parts. A producer who under-declares is refused by name — in a
raw proposal, and again when the same behaviour is hidden inside
a definition.
"""
from jacquard import Sequencer, make_envelope, records

DISPATCH_JOB = {"name": "dispatch-job",
                "signature": {"ins": ["map"], "outs": []},
                "body": ["dispatch"],
                "examples": [{"args": [{"job": "job-1"}],
                              "requests": ["dispatch"]}]}


def test_raw_underdeclared_proposal_refused_by_name():
    seq = Sequencer()
    verdict = seq.submit(make_envelope(
        "agent-a", "proposal",
        {"requests": [{"verb": "dispatch", "args": [{"job": "x"}]}]},
        ["reads"], "c2-a"))
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"
    view = records(seq.log.entries)
    assert view["agent-a"]["work"]["faults"] == 1


def test_dishonest_definition_refused_at_define_time():
    seq = Sequencer()
    dishonest = dict(DISPATCH_JOB)
    dishonest["name"] = "quiet-dispatch"
    dishonest["declared_effects"] = ["reads"]
    verdict = seq.submit(make_envelope(
        "agent-a", "definition", dishonest, ["reads"], "c2-b"))
    assert verdict["status"] == "REFUSED"
    assert verdict["refusal"] == "UNDERDECLARED"
    assert "quiet-dispatch" not in seq.state.dictionary


def test_honest_definition_computed_effects_drive_the_gate():
    seq = Sequencer()
    verdict = seq.submit(make_envelope(
        "agent-a", "definition", DISPATCH_JOB, ["dispatch"], "c2-c"))
    assert verdict["status"] == "accepted"
    assert verdict["computed_effects"] == ["dispatch"]
    stored = seq.state.dictionary["dispatch-job"][-1]["definition"]
    assert stored["computed_effects"] == ["dispatch"]
    # Evaluating the word emits a dispatch request and executes
    # nothing.
    entries_before = len(seq.log.entries)
    stack, requests = seq.evaluate_word("dispatch-job", "agent-a",
                                        [{"job": "job-9"}])
    assert stack == []
    assert requests == [{"verb": "dispatch", "args": [{"job": "job-9"}]}]
    assert len(seq.log.entries) == entries_before
    # Submitted honestly, the request is decided on its computed
    # effects. Submitted as "reads", it is refused: the word
    # cannot launder its effects through a definition.
    ok = seq.submit(make_envelope(
        "agent-a", "proposal", {"requests": requests},
        stored["computed_effects"], "c2-d"))
    assert ok["status"] == "decided" and ok["outcome"] == "allow"
    laundered = seq.submit(make_envelope(
        "agent-a", "proposal", {"requests": requests}, ["reads"], "c2-e"))
    assert laundered["status"] == "REFUSED"
    assert laundered["refusal"] == "UNDERDECLARED"
