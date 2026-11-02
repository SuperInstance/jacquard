"""Replay the real gpu-queue record through the Jacquard kernel.

The successor rule lives in tests/acceptance/queue_dictionary.py
as dictionary definitions. This harness only stages the recorded
facts (queue contents, feeder state, the foreign-work sense) and
executes the requests that evaluating `maybe-dispatch` returns.
Every dispatch in the report was therefore decided by the
dictionary, not by code in this file.

Dataset: tests/data/gpu-queue/ (see its PROVENANCE.md). Two
reconstructions are disclosed there and here:

- the feeder was enabled throughout the recorded run (it is
  disabled in the status snapshot taken days later; that the run
  happened at all under the daemon's rule, materialising 1,635
  feeder jobs, establishes it);
- the foreign-work sense is false at every recorded dispatch,
  because a dispatch happened (a foreign tick pre-empts it).

Replay is at decision granularity, not at the daemon's 20-second
tick granularity.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "tests", "acceptance"))

from jacquard import Sequencer, make_envelope  # noqa: E402
import queue_dictionary  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..",
                    "tests", "data", "gpu-queue")


def load_record(data_dir=DATA):
    with open(os.path.join(data_dir, "queue.json"),
              encoding="utf-8") as fh:
        queue = json.load(fh)
    job_ids = [job["id"] for job in queue["jobs"]]
    events = []
    with open(os.path.join(data_dir, "events.jsonl"),
              encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return job_ids, events


def _submit_write(seq, unit, value, idem):
    return seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": [unit, value]}]},
        ["write"], idem))


def run_replay(data_dir=DATA):
    job_ids, _events = load_record(data_dir)
    seq = Sequencer()
    for verdict in queue_dictionary.submit_all(seq):
        if verdict["status"] != "accepted":
            raise AssertionError("dictionary refused: %r" % (verdict,))
    _submit_write(seq, "gpu/queue", list(job_ids), "replay-init-queue")
    _submit_write(seq, "gpu/feeder", {"enabled": True}, "replay-init-feeder")
    _submit_write(seq, "gpu/holds", [], "replay-init-holds")
    _submit_write(seq, "gpu/start-failures", 0, "replay-init-failures")
    seq.submit_sense("gpu-foreign", False, "operator")

    dispatched = []
    holds = []
    evaluations = 0
    remaining = list(job_ids)
    steps = 0
    while remaining and steps <= len(job_ids) + 2:
        steps += 1
        _stack, requests = seq.evaluate_word("maybe-dispatch", "operator")
        evaluations += 1
        verbs = [r["verb"] for r in requests]
        if verbs == ["dispatch"]:
            job = requests[0]["args"][0]["job"]
            if job != remaining[0]:
                raise AssertionError(
                    "dictionary dispatched %s, head of queue is %s"
                    % (job, remaining[0]))
            # The executor applies the dispatch and advances the
            # queue atomically, as one proposal.
            seq.submit(make_envelope(
                "gpu-queue-daemon", "proposal",
                {"requests": [
                    {"verb": "dispatch", "args": [{"job": job}]},
                    {"verb": "write",
                     "args": ["gpu/queue", remaining[1:]]}]},
                ["dispatch", "write"], "replay-dispatch-%d" % steps))
            dispatched.append(job)
            remaining = remaining[1:]
        elif verbs == ["write"]:
            seq.submit(make_envelope(
                "gpu-queue-daemon", "proposal",
                {"requests": requests}, ["write"],
                "replay-hold-%d" % steps))
            holds.append(remaining[0])
            # A held job waits for a successor or the feeder;
            # neither changes inside the recorded window, so the
            # replay stops here rather than spinning.
            break
        elif verbs == []:
            break
        else:
            raise AssertionError("unexpected requests: %r" % (requests,))
    return {"dispatched": dispatched, "holds": holds,
            "evaluations": evaluations,
            "entries": len(seq.log.entries),
            "chain_ok": seq.log.verify_chain()}


if __name__ == "__main__":
    report = run_replay()
    job_ids, events = load_record()
    recorded = [e["job"] for e in events if e["event"] == "dispatch"]
    print(json.dumps({
        "dispatched": len(report["dispatched"]),
        "holds": report["holds"],
        "evaluations": report["evaluations"],
        "matches_queue_order": report["dispatched"] == job_ids,
        "matches_event_record": report["dispatched"] == recorded,
        "log_entries": report["entries"],
        "chain_ok": report["chain_ok"],
    }, indent=1))
