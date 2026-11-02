"""Budgets, prices, and senses (SPEC section 11).

The accounting test is the acceptance shape: spends replayed
from the log must reconstruct balances to the unit.
"""
import pytest

from jacquard import (Refusal, Sequencer, compute_sense, fold,
                      make_envelope, publish_senses)
from jacquard.scheduler import Scheduler


def spend_proposal(producer, resource, amount, ident):
    return make_envelope(producer, "proposal",
                         {"requests": [{"verb": "spend",
                                        "args": [resource, amount]}]},
                         ["spend"], ident)


def test_spend_accounting_replays_from_the_log_to_the_unit():
    seq = Sequencer()
    seq.grant_budget("operator", 100)
    seq.post_price("compute", 3)
    verdict = seq.submit(spend_proposal("operator", "compute", 5, "sp-1"))
    assert verdict["outcome"] == "allow"
    # 100 - 5 units at price 3 = 85, and a fresh fold of the log
    # alone must reconstruct exactly that.
    assert seq.state.budgets["operator"] == 85
    replayed = fold(seq.log.entries)
    assert replayed.budgets == seq.state.budgets
    assert replayed.state_hash() == seq.state.state_hash()


def test_spend_before_any_price_charges_the_default_price():
    seq = Sequencer()
    seq.grant_budget("operator", 10)
    seq.submit(spend_proposal("operator", "compute", 4, "sp-2"))
    assert seq.state.budgets["operator"] == 6  # default price 1


def test_price_change_applies_from_its_point_in_the_log():
    seq = Sequencer()
    seq.grant_budget("operator", 100)
    seq.post_price("compute", 2)
    seq.submit(spend_proposal("operator", "compute", 5, "sp-3"))
    seq.post_price("compute", 10)
    seq.submit(spend_proposal("operator", "compute", 5, "sp-4"))
    assert seq.state.budgets["operator"] == 100 - 10 - 50
    assert fold(seq.log.entries).budgets == seq.state.budgets


def test_buy_weight_charges_budget_and_records_evidence():
    seq = Sequencer()
    seq.grant_budget("alice", 50)
    seq.post_price("compute", 5)
    result = seq.buy_weight("alice", "work", 4)
    assert result["cost"] == 20
    assert result["balance"] == 30
    assert result["weight"] == 5.0
    assert fold(seq.log.entries).budgets["alice"] == 30
    purchases = [e for e in seq.log.entries if e["kind"] == "budget"
                 and e["body"].get("reason") == "weight-purchase"]
    assert len(purchases) == 1
    assert purchases[0]["body"]["extra"] == 4


def test_buy_weight_beyond_budget_is_a_conservation_refusal():
    seq = Sequencer()
    seq.grant_budget("alice", 10)
    with pytest.raises(Refusal) as caught:
        seq.buy_weight("alice", "work", 11)
    assert caught.value.name == "CONSERVATION"
    assert seq.state.budgets["alice"] == 10  # nothing was charged


# ---------------------------------------------------------- senses

def test_queue_depth_sense():
    seq = Sequencer()
    seq.submit(make_envelope("alice", "proposal",
                             {"requests": [{"verb": "notify",
                                            "args": ["ops", "hi"]}]},
                             ["notify"], "sn-1"))
    reading = compute_sense("queue-depth", seq.log.entries, seq.state)
    assert reading["value"] == 1
    assert "decision_queue" in reading["method"]


def test_computing_a_sense_appends_nothing():
    seq = Sequencer()
    before = len(seq.log.entries)
    compute_sense("queue-depth", seq.log.entries, seq.state)
    compute_sense("calibration-drift", seq.log.entries, seq.state)
    assert len(seq.log.entries) == before


def test_output_use_sense_reports_basis_points():
    seq = Sequencer()
    seq.submit(make_envelope(
        "factory", "proposal",
        {"requests": [{"verb": "write", "args": ["asset/1", {"x": 1}],
                       "outputs": ["asset-1"]}]},
        ["write"], "sn-2"))
    reading = compute_sense("output-use:factory", seq.log.entries,
                            seq.state)
    assert reading["value"]["outputs"] == 1
    assert reading["value"]["used"] == 0
    assert reading["value"]["ratio_bp"] == 0


def test_starvation_sense_with_and_without_runtime():
    seq = Sequencer()
    reading = compute_sense("starvation", seq.log.entries, seq.state)
    assert reading["value"] == {"status": "no-runtime"}
    sched = Scheduler()
    sched.submit(("alice", "work"), "x")
    reading = compute_sense("starvation", seq.log.entries, seq.state,
                            runtime={"scheduler": sched})
    assert reading["value"]["flows"]["alice/work"]["waiting"] == 1


def test_calibration_drift_stub_is_honest_about_being_a_stub():
    seq = Sequencer()
    reading = compute_sense("calibration-drift", seq.log.entries,
                            seq.state)
    assert reading["value"]["status"] == "insufficient-data"
    assert "stub" in reading["method"]


def test_publish_senses_writes_named_readings():
    seq = Sequencer()
    entries = publish_senses(seq, ["queue-depth"])
    assert entries[0]["kind"] == "sense"
    published = seq.state.senses["queue-depth"]
    assert published["value"] == 0
    assert published["method"]
    assert published["as_of_seq"] == entries[0]["seq"] - 1
