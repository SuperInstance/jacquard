"""Generate conformance/full-log.json.gz: a log that exercises
every entry kind the kernel emits, with the expected folded
state hash. Coordinator-side fixture tooling (Python); the
TypeScript checker folds the result from the spec alone.

The scenario: kernel A runs lifecycles, definitions, budgets,
prices, spends, a queued+released proposal, senses, a mined
rule taken to canary, and a checkpoint; its state is exported
and imported into fresh kernel B; B then grants, posts a price,
publishes a sense, queues a proposal, and checkpoints. The
fixture is B's log: between the import and B's own work it
contains all eleven emitted kinds (proposal entries are
reserved and never emitted; see spec section 2.1).
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jacquard import (Learner, Sequencer, export_bundle,  # noqa: E402
                      import_bundle, install_lifecycles, make_envelope,
                      publish_senses)

EMITTED = {"sense", "definition", "decision", "execution",
           "checkpoint", "machine", "transition", "budget",
           "price", "rule", "import"}


def submit_n(seq, producer, cls, verb, args, count, prefix):
    for i in range(count):
        seq.submit(make_envelope(
            producer, "proposal",
            {"class": cls, "requests": [{"verb": verb, "args": args}]},
            [verb], "%s-%d" % (prefix, i)))


def build_source():
    seq = Sequencer()
    install_lifecycles(seq)
    seq.submit(make_envelope("operator", "definition", {
        "name": "double",
        "signature": {"ins": ["int"], "outs": ["int"]},
        "body": ["dup", "add"],
        "examples": [{"args": [21], "expect": [42]}]}, [], "s-def"))
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "write", "args": ["answer", 42]}]},
        ["write"], "s-write"))
    seq.grant_budget("gpu-daemon", 500)
    seq.post_price("compute", 3)
    seq.submit(make_envelope(
        "operator", "proposal",
        {"requests": [{"verb": "spend", "args": ["compute", 5]}]},
        ["spend"], "s-spend"))
    verdict = seq.submit(make_envelope(
        "alice", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "hi"]}]},
        ["notify"], "s-queue"))
    seq.release_queued(verdict["proposal_id"], "operator")
    seq.submit_sense("gpu-foreign", False, "operator")
    publish_senses(seq, ["queue-depth"])
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
             [{"job": "j"}], 30, "s-gpu")
    learner = Learner()
    candidate = learner.mine(seq.log.entries)[0]
    learner.register(seq, candidate)
    submit_n(seq, "gpu-daemon", "gpu-queue", "dispatch",
             [{"job": "j"}], 4, "s-s")
    learner.promote(seq, candidate["rule_id"])
    seq.checkpoint("source-done")
    return seq


def main():
    source = build_source()
    dest = Sequencer()
    import_bundle(dest, export_bundle(source))
    dest.grant_budget("bob", 25)
    dest.post_price("compute", 2)
    publish_senses(dest, ["queue-depth"])
    dest.submit(make_envelope(
        "bob", "proposal",
        {"requests": [{"verb": "notify", "args": ["ops", "later"]}]},
        ["notify"], "d-queue"))
    dest.checkpoint("dest-done")
    kinds = {entry["kind"] for entry in dest.log.entries}
    missing = EMITTED - kinds
    if missing:
        raise SystemExit("fixture misses kinds: %s" % sorted(missing))
    out = {"entries": dest.log.entries,
           "expected_state_hash": dest.state.state_hash(),
           "entry_count": len(dest.log.entries)}
    path = os.path.join(os.path.dirname(__file__), "full-log.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(out, fh, sort_keys=True, indent=1)
    print("wrote %s: %d entries, kinds %s, hash %s"
          % (path, out["entry_count"], sorted(kinds),
             out["expected_state_hash"]))


if __name__ == "__main__":
    main()
