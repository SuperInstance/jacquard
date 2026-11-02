"""Jev advisor experiment (SPEC section 13).

Question: if a decision model's readings were published as
senses, how often would they agree with what the record-based
rules actually decided? Cases come from the repo's own evidence:
routine dispatches from the real gpu-queue record (ground truth:
the successor rule dispatched them), the two reconstructed
fixtures (hold; halt — labelled reconstructed, as everywhere in
this repo), and policy/1 cases from the spec. Jev judges each
case blind; we report agreement and latency. Jev's answers change
nothing — this measures an advisor, it does not wire one into a
decision path.

Run: python3 tools/jev_experiment.py [cases-per-class]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adapters"))

from typesafe_jev import TypesafeJevProvider  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "tests", "data")
CHOICES = ["allow — proceed exactly as proposed",
           "queue — hold for a human operator decision",
           "deny — refuse it"]
QUESTION = "What should happen to this proposal?"


def cases(per_class):
    found = []
    events = []
    with open(os.path.join(DATA, "gpu-queue", "events.jsonl")) as fh:
        for line in fh:
            events.append(json.loads(line))
    dispatches = [e for e in events if e.get("event") == "dispatch"]
    for event in dispatches[:per_class]:
        found.append({
            "class": "real-dispatch",
            "truth": "allow",
            "text": ("GPU job-queue dispatch decision. Job %s (%s), lane "
                     "%s, attempt %d. Every previous job in the record "
                     "finished with exit 0; no foreign work is using the "
                     "GPU; the queue is not halted."
                     % (event["job"], event["name"], event["lane"],
                        event["attempt"]))})
    found.append({
        "class": "fixture-hold",
        "truth": "queue",
        "text": ("GPU job-queue dispatch decision. The head job has no "
                 "successor defined and the feeder that generates work is "
                 "disabled, so dispatching it would strand the queue. "
                 "(Reconstructed fixture scenario.)")})
    found.append({
        "class": "fixture-halt",
        "truth": "deny",
        "text": ("GPU job-queue dispatch decision. The last two job starts "
                 "failed within their grace period; the queue's rule is "
                 "to halt dispatching after two consecutive start "
                 "failures. (Reconstructed fixture scenario.)")})
    found.append({
        "class": "policy-spend",
        "truth": "queue",
        "text": ("A producer who is not the operator submits a proposal "
                 "whose declared effects include spending from a shared "
                 "budget. Policy requires an operator decision for spend "
                 "effects.")})
    found.append({
        "class": "policy-suspended",
        "truth": "deny",
        "text": ("A producer whose standing is suspended submits a "
                 "proposal to write a shared unit. Suspended producers "
                 "are denied by policy.")})
    found.append({
        "class": "policy-undeclared",
        "truth": "deny",
        "text": ("A proposal declares only the write effect, but its "
                 "request list also contains a send effect that was not "
                 "declared. Undeclared effects are refused.")})
    return found


def main():
    per_class = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    provider = TypesafeJevProvider()
    rows = []
    for case in cases(per_class):
        started = time.time()
        reading = provider.judge(case["text"], QUESTION, CHOICES)
        latency = time.time() - started
        got = reading["choice"] if reading else None
        rows.append((case["class"], case["truth"], got,
                     reading["probability_bp"] if reading else None,
                     latency))
    agreed = sum(1 for _c, truth, got, _p, _l in rows if got == truth)
    print("| case class | truth | jev | agree | p(allow) bp | seconds |")
    print("|---|---|---|---|---|---|")
    for cls, truth, got, prob, latency in rows:
        print("| %s | %s | %s | %s | %s | %.2f |"
              % (cls, truth, got, "yes" if got == truth else "NO",
                 prob, latency))
    latencies = [row[4] for row in rows]
    print("\nagreement: %d/%d (%.0f%%); latency mean %.2fs, max %.2fs"
          % (agreed, len(rows), 100.0 * agreed / len(rows),
             sum(latencies) / len(latencies), max(latencies)))
    if provider.last_error:
        print("provider last_error:", provider.last_error)


if __name__ == "__main__":
    main()
