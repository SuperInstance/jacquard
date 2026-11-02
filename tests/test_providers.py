"""The decision-model provider seam (SPEC section 13).

Constitutional tests: a provider's reading is a sense; the
kernel's decision path imports no provider code; decisions are
identical with and without a judgement published.
"""
import os

from jacquard import (FakeProvider, NullProvider, RecordingProvider,
                      Sequencer, make_envelope, publish_judgement)

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "jacquard")


def test_judgement_is_published_as_a_sense_with_provider_named():
    seq = Sequencer()
    provider = FakeProvider([{"choice": "yes", "probability_bp": 7200,
                              "detail": "scripted"}])
    entry = publish_judgement(seq, provider, "judgement:triage",
                              "some text", "Is it safe?")
    assert entry["kind"] == "sense"
    reading = seq.state.senses["judgement:triage"]
    assert reading["value"]["provider"] == "fake"
    assert reading["value"]["probability_bp"] == 7200
    assert "advisor only" in reading["method"]


def test_null_provider_publishes_nothing():
    seq = Sequencer()
    before = len(seq.log.entries)
    assert publish_judgement(seq, NullProvider(), "judgement:x",
                             "t", "q?") is None
    assert len(seq.log.entries) == before


def test_recording_provider_keeps_the_evidence():
    inner = FakeProvider([{"choice": "no", "probability_bp": 1000,
                           "detail": ""}])
    provider = RecordingProvider(inner)
    provider.judge("text", "q?", ["yes", "no"])
    assert provider.calls[0]["reading"]["choice"] == "no"
    assert provider.name == "recording:fake"


def test_kernel_decision_path_imports_no_provider_code():
    for module in ("sequencer.py", "policy.py", "dictionary.py",
                   "state.py", "log.py"):
        with open(os.path.join(SRC, module)) as fh:
            assert "providers" not in fh.read(), module
        with open(os.path.join(SRC, module)) as fh:
            assert "typesafe" not in fh.read().lower(), module


def test_a_published_judgement_never_changes_a_decision():
    def run(with_judgement):
        seq = Sequencer()
        if with_judgement:
            provider = FakeProvider([{"choice": "yes",
                                      "probability_bp": 9900,
                                      "detail": "model says fine"}])
            publish_judgement(seq, provider, "judgement:spend",
                              "spend request", "Approve?")
        verdict = seq.submit(make_envelope(
            "alice", "proposal",
            {"requests": [{"verb": "spend", "args": ["compute", 5]}]},
            ["spend"], "pv-1"))
        return verdict["outcome"], len(seq.state.decision_queue)

    assert run(False) == run(True) == ("queue", 1)
