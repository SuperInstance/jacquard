"""Probe A (Phase 4, F1): contention over committed state.

Sections, mirroring the probe brief:

a. The rung-1 wall, in three exhibits: the inventory of
   list-consuming primitives/forms (none applies a per-element
   predicate -- ``first`` is the only one that yields an element,
   and only the first); a first-only word whose wrong answer is
   exhibited against a reference label; a count-only pair of
   states no count can distinguish. Plus: ``sum`` over a list of
   maps raises Refusal FIELD -- there is no field projection.
b. The rung-4 contention sense against the REAL board corpus:
   all 52 decided items replayed through one Sequencer (sense ->
   dictionary guards -> booking machine, no harness predicates),
   including the three incumbent-wrong double-bookings; refold
   hash equality; republish determinism.
c. The independently authored adversarial corpus
   (adversarial_a.json). All 35 cases match exactly. Two of
   them turn on candidate-id identity (a committed row reusing
   the candidate's id under a different producer): the sense's
   subject grammar -- <box>/<seat>/<start>/<end>/<producer>/
   <id> -- carries the candidate id as its final field, so the
   sense expresses the identity skip ("a booking never contends
   with itself") and matches those cases too, as does the fold
   form in (f).
d. The staleness hazard, pinned: a guard reads the PUBLISHED
   sense reading, so publishing must happen at decision time.
e. Costs: the sense at 10/100/1000 committed bookings (medians
   of 20), and folding the 3,295-entry conformance replay log
   as the replay baseline.
f. The rung-5 ``any`` fold form, measured not advocated: the
   C2 computed-effects hazard under the stock token walk, the
   catch under a descending walk, agreement with the reference
   labels on the real corpus AND with the adversarial corpus's
   expected labels (all 35), and its evaluation + layout costs
   against the sense's.

Everything runs on fresh Sequencers; nothing here edits src/.
"""
import gzip
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import pytest  # noqa: E402

from jacquard import Sequencer, fold, make_envelope  # noqa: E402
from jacquard.canonical import canonical  # noqa: E402
from jacquard.primitives import SYNTAX_FORMS, TIER_P  # noqa: E402
from jacquard.senses import compute_sense  # noqa: E402
from jacquard.state import Refusal, State  # noqa: E402

import booking_flow  # noqa: E402
import corpus  # noqa: E402
import fold_experiment  # noqa: E402
from contention_sense import contention_sense, register  # noqa: E402

register()

PROBES_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROBES_DIR.parents[1]

CANDIDATE = {"id": "cand", "box": "thor", "producer": "lane-b",
             "seat": "gpu", "start": 1100, "end": 1300,
             "checkby": None, "status": "active", "rank": 0}


def booking(id_, producer="lane-a", seat="gpu", start=1000, end=1200,
            box="thor", checkby=None, status="active", rank=0):
    return {"id": id_, "box": box, "producer": producer, "seat": seat,
            "start": start, "end": end, "checkby": checkby,
            "status": status, "rank": rank}


def kernel():
    seq = Sequencer()
    booking_flow.install(seq)
    return seq


def sense_value_for(seq, candidate):
    name = booking_flow.publish_contention(seq, candidate)
    return seq.state.senses[name]["value"]


# ------------------------------------------------------------ (a) rung 1

def test_a_inventory_of_list_consumers():
    """Exhibit (i): the complete set of list-consuming
    primitives/forms is exactly the eight named in the brief,
    and none of them applies a per-element predicate."""
    list_prims = {name for name, (ins, _outs) in TIER_P.items()
                  if "list" in ins}
    assert list_prims == {"count", "sum", "min", "max", "contains"}
    list_forms = {"first", "snoc", "cat"}
    assert list_forms <= SYNTAX_FORMS
    assert list_prims | list_forms == {
        "count", "sum", "min", "max", "contains", "first", "snoc",
        "cat"}
    # Aggregates return a reduction (int / bool / extremum),
    # snoc/cat build values; `first` alone yields an element,
    # and by construction only element 0 -- no form takes a
    # predicate or yields an element chosen by a per-element test.
    outs = {name: TIER_P[name][1] for name in list_prims}
    assert outs["count"] == ["int"] and outs["sum"] == ["int"]
    assert outs["contains"] == ["bool"]


def test_a_first_only_counterexample():
    """Exhibit (ii): a word that checks contention against ONLY
    the first booking of bookings/<box> defines and runs -- and
    answers "clear" where the reference label is contended,
    because the contending booking is the SECOND element."""
    seq = Sequencer()
    defn = fold_experiment.pair_contends_definition()
    verdict = seq.submit(make_envelope(
        "operator", "definition", defn, [], "probe-a-a-pair"))
    assert verdict["status"] == "accepted", verdict
    first = booking("o-first", start=2000, end=2200)     # disjoint
    second = booking("o-second", start=1000, end=1200)   # contends
    word = {
        "name": "first-only-clear",
        "signature": {"ins": ["map"], "outs": ["bool"]},
        "body": ["dup", {"lit": "box"}, "getf",
                 {"lit": "bookings/"}, "swap", "cat", "get",
                 "first", "pair-contends", "not"],
        "examples": [{
            "args": [dict(CANDIDATE)],
            "state": {"units": {"bookings/thor": [first, second]}},
            "expect": [True]}]}  # the word's own (wrong) answer
    verdict = seq.submit(make_envelope(
        "operator", "definition", word, [], "probe-a-a-first"))
    assert verdict["status"] == "accepted", verdict
    # Commit the same two bookings as a list unit and evaluate.
    seq.submit(make_envelope(
        "lane-a", "proposal",
        {"class": "booking", "requests": [
            {"verb": "write",
             "args": ["bookings/thor", [first, second]]}]},
        ["write"], "probe-a-a-commit"))
    stack, _ = seq.evaluate_word("first-only-clear", "operator",
                                 [dict(CANDIDATE)])
    assert stack == [True]  # word says: clear
    # Reference label, from the contention sense over per-id
    # units holding the same two bookings: contended.
    state = State()
    for b in (first, second):
        state.units["booking/thor/%s" % b["id"]] = b
    reading = contention_sense([], state,
                               "thor/gpu/1100/1300/lane-b/cand", None)
    assert reading["value"]["count"] == 1
    assert reading["value"]["contenders"][0]["id"] == "o-second"
    # The word's answer is therefore wrong, by construction.


def test_a_count_only_counterexample():
    """Exhibit (iii): two committed states with the SAME booking
    count (2) for the candidate's box and the same candidate;
    one is contended, the other is not. Any count-based reading
    sees the same number for both, so it cannot distinguish
    them -- the labels differ."""
    cand_subject = "thor/gpu/1100/1300/lane-b/cand"
    contended_state = State()
    contended_state.units["booking/thor/o1"] = booking("o1")
    contended_state.units["booking/thor/o2"] = booking(
        "o2", start=2000, end=2200)
    clear_state = State()
    clear_state.units["booking/thor/o3"] = booking(
        "o3", start=2000, end=2200)
    clear_state.units["booking/thor/o4"] = booking(
        "o4", seat="detached", start=3000, end=3200)
    counts = []
    labels = []
    for state in (contended_state, clear_state):
        counts.append(sum(1 for u in state.units
                          if u.startswith("booking/thor/")))
        labels.append(contention_sense([], state, cand_subject,
                                       None)["value"]["count"] > 0)
    assert counts == [2, 2]          # counts equal ...
    assert labels == [True, False]   # ... labels differ


def test_a_sum_over_list_of_maps_is_a_field_refusal():
    """There is no field projection: `sum` over a list of maps
    cannot extract a numeric field, and refuses by name."""
    seq = Sequencer()
    defn = {"name": "sum-unit",
            "signature": {"ins": ["str"], "outs": ["int"]},
            "body": ["get", "sum"],
            "examples": [{"args": ["nums"], "expect": [3],
                          "state": {"units": {"nums": [1, 2]}}}]}
    verdict = seq.submit(make_envelope(
        "operator", "definition", defn, [], "probe-a-a-sum"))
    assert verdict["status"] == "accepted", verdict
    seq.submit(make_envelope(
        "lane-a", "proposal",
        {"class": "booking", "requests": [
            {"verb": "write",
             "args": ["bookings/thor", [booking("o1")]]}]},
        ["write"], "probe-a-a-sum-commit"))
    with pytest.raises(Refusal) as caught:
        seq.evaluate_word("sum-unit", "operator", ["bookings/thor"])
    assert caught.value.name == "FIELD"


# ------------------------------------------------------- (b) real corpus

@pytest.fixture(scope="module")
def built():
    if not (corpus.DEFAULT_INBOX / ".git").exists():
        pytest.skip("agent-inbox corpus absent at %s; the "
                    "real-corpus probes run where the fleet "
                    "board lives" % corpus.DEFAULT_INBOX)
    data = corpus.build()
    corpus.self_test(data)
    return data


def test_b_corpus_self_test_counts(built):
    summary = corpus.self_test(built)
    assert summary == {"items": 68, "notes": 6, "unevaluable": 10,
                       "decided": 52, "contended": 6, "events": 148,
                       "by_type": {"candidate": 52, "commit": 58,
                                   "status": 38}}


def test_b_sense_matches_all_52_real_candidates(built):
    seq = kernel()
    items = {i["index"]: i for i in built["items"]}
    current = {}
    decided = 0
    contended = 0
    contended_triples = set()
    for event in built["events"]:
        if event["type"] == "commit":
            verdict = booking_flow.commit_booking_record(
                seq, event["booking"])
            assert verdict["outcome"] == "allow", verdict
            current[event["booking"]["id"]] = dict(event["booking"])
        elif event["type"] == "status":
            verdict = booking_flow.set_booking_status(
                seq, event["id"], event["box"], event["status"],
                current[event["id"]])
            assert verdict["outcome"] == "allow", verdict
            current[event["id"]] = {**current[event["id"]],
                                    "status": event["status"]}
        elif event["type"] == "candidate":
            candidate = event["booking"]
            label = built["labels"][event["item"]]
            value = sense_value_for(seq, candidate)
            got_with = sorted(c["id"] for c in value["contenders"])
            want_with = sorted(items[i]["id"] for i in label["with"])
            assert got_with == want_with, (candidate["id"], value,
                                           label)
            assert (value["count"] > 0) == label["contends"]
            decision = booking_flow.shadow_decide(seq, candidate)
            assert decision == ("queue" if label["contends"]
                                else "allow"), (candidate, decision,
                                                label)
            decided += 1
            contended += label["contends"]
            if label["contends"]:
                item = items[event["item"]]
                contended_triples.add(
                    (item["box"], item["seat"], item["lane"]))
    assert decided == 52
    assert contended == 6
    # The three incumbent-wrong double-bookings from the trial
    # report are caught (as (box, seat, lane) triples; other
    # items share these lane names on other seats and are not
    # the report's items).
    assert {("proart", "box", "otherhere-rebuild"),
            ("thor", "box", "eden-trial"),
            ("thor", "box", "whole-house-stage0")} <= contended_triples
    # Refold: the log alone reconstructs the sequencer's state.
    refolded = fold(seq.log.entries)
    assert refolded.state_hash() == seq.state.state_hash()
    # Determinism: publishing the same sense twice in a row (no
    # intervening commit) yields byte-identical values.
    probe = booking("bk-probe", producer="lane-z", start=5000,
                    end=5100)
    name1 = booking_flow.publish_contention(seq, probe)
    first = canonical(seq.state.senses[name1]["value"])
    name2 = booking_flow.publish_contention(seq, probe)
    assert name1 == name2
    assert canonical(seq.state.senses[name2]["value"]) == first


# --------------------------------------------------- (c) adversarial

def _load_adversarial():
    path = PROBES_DIR / "adversarial_a.json"
    if not path.exists():
        pytest.skip("adversarial_a.json absent (authored "
                    "independently); skipping the adversarial run")
    return json.loads(path.read_text(encoding="utf-8"))


def test_c_adversarial_runner():
    data = _load_adversarial()
    cases = data["cases"]
    assert len(cases) == 35
    matched = 0
    candidate_checks = 0
    for case in cases:
        seq = kernel()
        current = {}

        def decide(candidate):
            value = sense_value_for(seq, candidate)
            decision = booking_flow.shadow_decide(seq, candidate)
            return value, decision

        if "events" in case:
            for event in case["events"]:
                if "commit" in event:
                    b = event["commit"]
                    verdict = booking_flow.commit_booking_record(seq, b)
                    assert verdict["outcome"] == "allow", verdict
                    current[b["id"]] = dict(b)
                elif "status" in event:
                    booking_id, new_status = event["status"]
                    verdict = booking_flow.set_booking_status(
                        seq, booking_id, current[booking_id]["box"],
                        new_status, current[booking_id])
                    assert verdict["outcome"] == "allow", verdict
                    current[booking_id] = {**current[booking_id],
                                            "status": new_status}
                elif "candidate" in event:
                    value, decision = decide(event["candidate"])
                    expected = event["expected"]
                    assert (value["count"] > 0) == expected["contends"], \
                        (case["name"], value, expected)
                    assert sorted(c["id"] for c in value["contenders"]) \
                        == sorted(expected["with"]), (case["name"], value)
                    assert decision == ("queue" if expected["contends"]
                                        else "allow")
                    candidate_checks += 1
            matched += 1
            continue
        for b in case["committed"]:
            verdict = booking_flow.commit_booking_record(seq, b)
            assert verdict["outcome"] == "allow", verdict
        value, decision = decide(case["candidate"])
        expected = case["expected"]
        got_with = sorted(c["id"] for c in value["contenders"])
        # Exact agreement, including the two candidate-id cases
        # (duplicate-id-different-producer-excluded and
        # back-to-back-touching-neighbours): the sense subject
        # now carries the candidate id, so a committed row
        # reusing that id is excluded as the candidate itself.
        assert (value["count"] > 0) == expected["contends"], \
            (case["name"], value, expected)
        assert got_with == sorted(expected["with"]), \
            (case["name"], value, expected)
        assert decision == ("queue" if expected["contends"]
                            else "allow")
        matched += 1
        candidate_checks += 1
    # 35 exact matches (33 static + 2 temporal),
    # 37 candidate decisions in total.
    assert matched == 35, matched
    assert candidate_checks == 37


# ------------------------------------------------------- (d) staleness

def test_d_staleness_hazard_publish_at_decision_time():
    seq = kernel()
    candidate = dict(CANDIDATE)
    name = booking_flow.publish_contention(seq, candidate)
    payload = {**candidate, "sense_name": name}
    stack, _ = seq.evaluate_word("booking-clear", "operator",
                                 [payload])
    assert stack == [True]  # clear, as published
    # Reality moves: an overlapping booking commits.
    verdict = booking_flow.commit_booking_record(seq, booking("o-late"))
    assert verdict["outcome"] == "allow"
    # The guard, evaluated against the STALE published reading,
    # still says clear. This is the documented hazard, asserted
    # as the pinned behaviour -- not a bug to be fixed here.
    stack, _ = seq.evaluate_word("booking-clear", "operator",
                                 [payload])
    assert stack == [True]
    # Republish at decision time: the guard now says contended.
    name2 = booking_flow.publish_contention(seq, candidate)
    assert name2 == name
    stack, _ = seq.evaluate_word("booking-clear", "operator",
                                 [payload])
    assert stack == [False]
    stack, _ = seq.evaluate_word("booking-contended", "operator",
                                 [payload])
    assert stack == [True]


# ------------------------------------------------------------ (e) cost

def _sense_state(n):
    state = State()
    for i in range(n):
        state.units["booking/thor/bk-%04d" % i] = booking(
            "bk-%04d" % i, producer="lane-%d" % i)
    return state


def _median_ms(fn, reps):
    times = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(times)


def test_e_cost_sense_and_fold_baseline(capsys):
    results = {}
    subject = "thor/gpu/1100/1300/lane-b/cand"
    for n in (10, 100, 1000):
        state = _sense_state(n)
        results["sense_%d" % n] = _median_ms(
            lambda: compute_sense("contention:" + subject, [], state),
            20)
    with gzip.open(REPO_ROOT / "conformance" / "replay-log.json.gz",
                   "rt", encoding="utf-8") as fh:
        replay = json.load(fh)
    entries = replay["entries"]
    assert len(entries) == 3295
    assert replay["entry_count"] == 3295

    def fold_once():
        folded = fold(entries)
        assert folded.state_hash() == replay["expected_state_hash"]

    results["fold_3295"] = _median_ms(fold_once, 3)
    print("PROBE-A COSTS (median ms):", json.dumps(
        {k: round(v, 3) for k, v in sorted(results.items())}))
    assert results["sense_1000"] < 50.0, results
    assert results["sense_10"] <= results["sense_1000"] + 5.0
    assert results["fold_3295"] > 0


# ------------------------------------------------------ (f) fold form

def test_f_c2_hazard_under_stock_walk():
    """SUPERSEDED 2026-11-02 (Phase 6, slice 17) — re-aimed at
    the closure. As written in Phase 4 this test asserted the
    hazard: with the stock _walk_tokens, a Tier-E verb hidden
    inside {"any": [...]} computed effects == [] while the
    FoldDictionary accepted the definition and its evaluation
    emitted the verb's requests. Spec 0.4 (sections 4-5) made
    the walk form-agnostic, so the same definition, accepted
    by the same extension, now computes the verb: the requests
    it emits are accounted. The stock kernel's own verdict on
    this body is asserted in tests/test_quotation_battery.py
    (REFUSED(SPEC), the form named)."""
    seq = Sequencer()
    fold_experiment.install_fold(seq)
    sneaky = {
        "name": "any-write",
        "signature": {"ins": ["list"], "outs": ["bool"]},
        "body": [{"any": ["drop", {"lit": "probe/sneaky"},
                          {"lit": 1}, "write", {"lit": True}]}],
        "examples": [{"args": [[7]], "expect": [True],
                      "requests": ["write"]}]}
    verdict = seq.submit(make_envelope(
        "operator", "definition", sneaky, [], "probe-a-f-sneaky"))
    assert verdict["status"] == "accepted", verdict
    assert verdict["computed_effects"] == ["write"]
    stored = seq.state.dictionary["any-write"][-1]["definition"]
    assert stored["computed_effects"] == ["write"]
    stack, requests = seq.evaluate_word("any-write", "operator",
                                        [[1, 2]])
    assert stack == [True]
    assert [r["verb"] for r in requests] == ["write", "write"]


def test_f_descending_walk_catches_the_verb(monkeypatch):
    """SUPERSEDED 2026-11-02 (Phase 6, slice 17) — re-aimed.
    As written in Phase 4 this test patched the stock walk
    with the prototype's descending walk to catch the verb.
    The stock walk now descends into every form itself, so it
    catches the verb unaided, and the prototype's walk —
    kept here as the historical artifact that demonstrated
    the fix — agrees with it."""
    import jacquard.dictionary as dictionary_module
    seq = Sequencer()
    fold_experiment.install_fold(seq)
    defn = {"name": "any-write",
            "signature": {"ins": ["list"], "outs": ["bool"]},
            "body": [{"any": ["drop", {"lit": "probe/sneaky"},
                              {"lit": 1}, "write", {"lit": True}]}],
            "examples": []}
    assert seq.dictionary.computed_effects(defn) == {"write"}
    monkeypatch.setattr(dictionary_module, "_walk_tokens",
                        fold_experiment.descending_walk_tokens)
    assert seq.dictionary.computed_effects(defn) == {"write"}


def _fold_replay_corpus(built):
    seq = Sequencer()
    fold_experiment.install_fold(seq)
    lists = {}
    decided = 0
    for event in built["events"]:
        if event["type"] == "commit":
            verdict = fold_experiment.commit_booking_list(
                seq, lists, event["booking"])
            assert verdict["outcome"] == "allow", verdict
        elif event["type"] == "status":
            verdict = fold_experiment.set_booking_list_status(
                seq, lists, event["box"], event["id"], event["status"])
            assert verdict["outcome"] == "allow", verdict
        elif event["type"] == "candidate":
            clear = fold_experiment.evaluate_clear_list(
                seq, event["booking"])
            label = built["labels"][event["item"]]
            assert clear == (not label["contends"]), \
                (event["booking"], clear, label)
            decided += 1
    assert decided == 52


def test_f_fold_agrees_on_real_corpus(built):
    _fold_replay_corpus(built)


def test_f_fold_agrees_on_adversarial_expected():
    """Against the adversarial corpus the fold form is compared
    with the EXPECTED labels (not with the sense): it matches
    all 35 cases, including the two candidate-id cases --
    pair-contends receives the whole candidate map, id included,
    and the sense now matches those cases as well since its
    subject grammar gained the candidate id as a final field."""
    data = _load_adversarial()
    checks = 0
    for case in data["cases"]:
        seq = Sequencer()
        fold_experiment.install_fold(seq)
        lists = {}
        if "events" in case:
            for event in case["events"]:
                if "commit" in event:
                    verdict = fold_experiment.commit_booking_list(
                        seq, lists, event["commit"])
                    assert verdict["outcome"] == "allow", verdict
                elif "status" in event:
                    booking_id, new_status = event["status"]
                    box = next(b["box"] for lst in lists.values()
                               for b in lst if b["id"] == booking_id)
                    verdict = fold_experiment.set_booking_list_status(
                        seq, lists, box, booking_id, new_status)
                    assert verdict["outcome"] == "allow", verdict
                elif "candidate" in event:
                    clear = fold_experiment.evaluate_clear_list(
                        seq, event["candidate"])
                    assert clear == (not event["expected"]["contends"]), \
                        (case["name"], clear, event["expected"])
                    checks += 1
            continue
        for b in case["committed"]:
            verdict = fold_experiment.commit_booking_list(seq, lists, b)
            assert verdict["outcome"] == "allow", verdict
        clear = fold_experiment.evaluate_clear_list(seq, case["candidate"])
        assert clear == (not case["expected"]["contends"]), \
            (case["name"], clear, case["expected"])
        checks += 1
    assert checks == 37


def test_f_fold_cost_and_layout_cost(capsys):
    results = {}
    for n in (100, 1000):
        bookings = [booking("bk-%04d" % i, producer="lane-%d" % i)
                    for i in range(n)]
        # Sense over the per-id layout.
        state = State()
        for b in bookings:
            state.units["booking/thor/%s" % b["id"]] = b
        results["sense_%d" % n] = _median_ms(
            lambda: compute_sense(
                "contention:thor/gpu/1100/1300/lane-b/cand", [], state), 20)
        # Fold word over the list layout.
        seq = Sequencer()
        fold_experiment.install_fold(seq)
        verdict = seq.submit(make_envelope(
            "operator", "proposal",
            {"class": "booking", "requests": [
                {"verb": "write", "args": ["bookings/thor", bookings]}]},
            ["write"], "probe-a-f-cost-%d" % n))
        assert verdict["outcome"] == "allow", verdict
        candidate = dict(CANDIDATE)
        results["fold_%d" % n] = _median_ms(
            lambda: fold_experiment.evaluate_clear_list(seq, candidate),
            20)
        results["list_value_bytes_%d" % n] = len(canonical(bookings))
    results["per_id_value_bytes"] = len(canonical(booking("bk-0000")))
    print("PROBE-A FOLD COSTS:", json.dumps(
        {k: (round(v, 3) if isinstance(v, float) else v)
         for k, v in sorted(results.items())}))
    # Layout cost: in the list layout every booking commit
    # rewrites the whole list, so the write value grows with the
    # number of bookings (~10x from 100 to 1000); in the per-id
    # layout the write value is one booking, constant.
    assert results["list_value_bytes_1000"] > \
        5 * results["list_value_bytes_100"]
    assert results["per_id_value_bytes"] < 200
    assert results["fold_1000"] > 0 and results["sense_1000"] > 0
