"""Decision-model providers: the advisor seam (SPEC section 13).

Decision models (Jev-class judgement models and their kin) may
play exactly one role in Jacquard: advisor. A provider's reading
is published as a sense — named evidence with its method and its
provider stated — and may be consumed as data by anything that
consults senses. No allow/deny path depends on a provider
verdict; the record gates, never the model.

This module is the seam, and it is deliberately outside the
kernel's decision path: the kernel (sequencer, policy,
dictionary) imports nothing from here, and no provider-specific
code lives in the kernel package at all. A deployment plugs in a
provider by implementing this interface — the first plugged-in
provider is Typesafe's Jev, via an adapter that lives outside
this package (adapters/typesafe_jev.py). Switching providers
changes which senses get published, never how decisions are
made.
"""


class DecisionModelProvider:
    """Interface. judge(text, question, choices) -> a reading:
    {"choice": one of choices or None,
     "probability_bp": integer basis points for the FIRST choice,
     or None, "detail": str}. Providers may decline (return None).
    """

    name = "abstract"

    def judge(self, text, question, choices):
        raise NotImplementedError


class NullProvider(DecisionModelProvider):
    """Publishes nothing. The default posture."""

    name = "null"

    def judge(self, text, question, choices):
        return None


class FakeProvider(DecisionModelProvider):
    """Scripted answers, for tests and drills. `answers` is a
    list of readings consumed in order, or a callable
    (text, question, choices) -> reading."""

    name = "fake"

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def judge(self, text, question, choices):
        self.calls.append({"text": text, "question": question,
                           "choices": list(choices)})
        if callable(self.answers):
            return self.answers(text, question, choices)
        return self.answers.pop(0)


class RecordingProvider(DecisionModelProvider):
    """Wraps a provider and keeps every call and reading, so an
    experiment can be replayed and audited."""

    def __init__(self, inner):
        self.inner = inner
        self.name = "recording:" + inner.name
        self.calls = []

    def judge(self, text, question, choices):
        reading = self.inner.judge(text, question, choices)
        self.calls.append({"text": text, "question": question,
                           "choices": list(choices), "reading": reading})
        return reading


def publish_judgement(sequencer, provider, name, text, question,
                      choices=("yes", "no"), producer="operator"):
    """Ask a provider and publish its reading as a sense. Returns
    the sense entry, or None when the provider declines. The
    reading lands in the record as evidence; nothing in the
    decision path is wired to it."""
    reading = provider.judge(text, question, list(choices))
    if reading is None:
        return None
    value = {"provider": provider.name,
             "question": question,
             "choice": reading.get("choice"),
             "probability_bp": reading.get("probability_bp"),
             "detail": reading.get("detail", "")}
    return sequencer.submit_sense(name, {
        "value": value,
        "method": "decision-model judgement via the provider "
                  "interface (section 13); advisor only — the "
                  "record gates, never the model",
        "as_of_seq": (sequencer.log.entries[-1]["seq"]
                      if sequencer.log.entries else -1)}, producer)
