"""State export bundles (SPEC section 14): the round-trip, the
shadow re-entry, and the tamper refusals.
"""
import copy

import pytest

from jacquard import (Learner, Refusal, Sequencer, export_bundle,
                      import_bundle, install_lifecycles, make_envelope,
                      rule_stage)


def submit_n(seq, producer, cls, verb, args, count, prefix):
    for i in range(count):
        seq.submit(make_envelope(
            producer, "proposal",
            {"class": cls, "requests": [{"verb": verb, "args": args}]},
            [verb], "%s-%d" % (prefix, i)))


def source_kernel():
    """Kernel A: lifecycles, a definition, committed units, a
    budget, and a standing rule driven all the way to active."""
    seq = Sequencer()
    install_lifecycles(seq)
    seq.submit(make_envelope("operator", "definition", {
        "name": "double",
        "signature": {"ins": ["int"], "outs": ["int"]},
        "body": ["dup", "add"],
        "examples": [{"args": [21], "expect": [42]}]}, [], "a-def"))
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": ["answer", 42]}]},
        ["write"], "a-write"))
    seq.grant_budget("gpu-daemon", 500)
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             30, "a-gpu")
    learner = Learner()
    candidate = learner.mine(seq.log.entries)[0]
    learner.register(seq, candidate)
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "a-s")
    learner.promote(seq, candidate["rule_id"])
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "a-c")
    learner.activate(seq, candidate["rule_id"])
    assert rule_stage(seq.state, candidate["rule_id"]) == "active"
    return seq, candidate["rule_id"]


def test_round_trip_between_two_kernels():
    source, rule_id = source_kernel()
    bundle = export_bundle(source)
    dest = Sequencer()
    report = import_bundle(dest, bundle)
    assert report["status"] == "imported"
    # configuration travelled as-is
    assert dest.state.units["answer"] == 42
    # definitions travelled and were re-proven on entry
    stored = dest.state.dictionary["double"][-1]["definition"]
    assert stored["computed_effects"] == []
    # machines travelled (all seven lifecycles)
    assert set(dest.state.machines) == set(source.state.machines)
    # the rule is present — at shadow, not active
    assert rule_stage(dest.state, rule_id) == "shadow"
    record = dest.state.rules[rule_id]
    assert record["origin"] == "imported"
    assert record["imported_from_stage"] == "active"
    # budgets never travel: the destination issued none
    assert dest.state.budgets == {}
    # the import itself is in the record
    imports = [e for e in dest.log.entries if e["kind"] == "import"]
    assert len(imports) == 1


def test_imported_rule_must_re_earn_activation():
    source, rule_id = source_kernel()
    dest = Sequencer()
    import_bundle(dest, export_bundle(source))
    learner = Learner()
    learner.install(dest)
    # shadow: it predicts but does not decide in the destination
    submit_n(dest, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "b-s")
    decision = [e for e in dest.log.entries if e["kind"] == "decision"][-1]
    assert "decided_by" not in decision["body"]
    # re-earning on the destination's own record
    learner.promote(dest, rule_id)
    submit_n(dest, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             4, "b-c")
    learner.activate(dest, rule_id)
    assert rule_stage(dest.state, rule_id) == "active"
    submit_n(dest, "gpu-daemon", "gpu-queue", "dispatch", [{"job": "j"}],
             1, "b-g")
    decision = [e for e in dest.log.entries if e["kind"] == "decision"][-1]
    assert decision["body"]["decided_by"] == rule_id


def test_reimport_is_idempotent_for_definitions_and_machines():
    source, _rule_id = source_kernel()
    dest = Sequencer()
    bundle = export_bundle(source)
    import_bundle(dest, bundle)
    machines_before = len(dest.log.entries)
    report = import_bundle(dest, bundle)
    assert "definition:double" in report["skipped"]
    assert any(item.startswith("machine:") for item in report["skipped"])
    assert len(dest.log.entries) > machines_before  # import entry only


def test_bundle_smuggling_a_credential_is_refused_by_name():
    source, _ = source_kernel()
    bundle = export_bundle(source)
    bundle["credentials"] = {"api_key": "should-not-travel"}
    dest = Sequencer()
    with pytest.raises(Refusal) as caught:
        import_bundle(dest, bundle)
    assert caught.value.name == "PROVENANCE"


def test_bundle_smuggling_a_budget_is_refused_by_name():
    source, _ = source_kernel()
    bundle = export_bundle(source)
    bundle["config"]["budgets"] = {"gpu-daemon": 1000000}
    dest = Sequencer()
    with pytest.raises(Refusal) as caught:
        import_bundle(dest, bundle)
    assert caught.value.name == "PROVENANCE"
    assert dest.state.budgets == {}


def test_rule_smuggling_an_active_stage_is_refused_by_name():
    source, _ = source_kernel()
    bundle = export_bundle(source)
    bundle["rules"][0]["stage"] = "active"
    dest = Sequencer()
    with pytest.raises(Refusal) as caught:
        import_bundle(dest, bundle)
    assert caught.value.name == "PROVENANCE"
    assert dest.state.rules == {}


def test_definition_smuggling_computed_effects_is_refused():
    source, _ = source_kernel()
    bundle = export_bundle(source)
    bundle["definitions"][0]["computed_effects"] = []
    dest = Sequencer()
    with pytest.raises(Refusal) as caught:
        import_bundle(dest, bundle)
    assert caught.value.name == "PROVENANCE"


def test_wrong_format_is_refused():
    dest = Sequencer()
    with pytest.raises(Refusal) as caught:
        import_bundle(dest, {"format": "something-else"})
    assert caught.value.name == "PROVENANCE"


def test_export_is_pure():
    source, _ = source_kernel()
    before = len(source.log.entries)
    export_bundle(source)
    assert len(source.log.entries) == before
