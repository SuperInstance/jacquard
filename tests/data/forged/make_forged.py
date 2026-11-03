"""Generate proof-run-2-forged.jsonl — the slice-18 attack fixture.

Reads the frozen Phase 6 proof log (docs/proof-run-2/kernel.jsonl),
rewrites ONE entry, and recomputes the internal hash chain from
that entry on, producing a log that is fully self-consistent
under the kernel's own chain verification (spec section 2) but is
not the anchored history. See PROVENANCE.md beside this script
for what was changed and why.

Run from anywhere:  python3 tests/data/forged/make_forged.py
(writes next to this script; deterministic — re-running
reproduces the committed fixture byte-for-byte).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from jacquard.canonical import canonical, hash_of  # noqa: E402
from jacquard.log import GENESIS_PREV  # noqa: E402

SOURCE = os.path.join(ROOT, "docs", "proof-run-2", "kernel.jsonl")
TARGET = os.path.join(HERE, "proof-run-2-forged.jsonl")
FORGE_SEQ = 100


def main():
    with open(SOURCE, "r", encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    target = entries[FORGE_SEQ]
    assert target["kind"] == "decision", target["kind"]
    assert target["body"]["outcome"] == "allow", target["body"]
    assert target["body"]["proposal_id"] == \
        "495d40460dfc5fa12e44c1ffa86dfdc33bcc8a8a1ffd4eb374597bdd9fffcc61"

    # The rewrite: the operator's release of that proposal is
    # flipped to a denial. Everything else about the entry —
    # including `released_by` and `releases` — is left as recorded,
    # exactly as a careless-or-motivated rewriter would leave it:
    # the point is that the CHAIN cannot tell.
    target["body"]["outcome"] = "deny"

    # Recompute the chain from FORGE_SEQ on: each entry's prev
    # becomes the previous entry's recomputed hash, and each hash
    # recomputes over (seq, prev, kind, body, spec) with the
    # entry's recorded spec preserved.
    prev = entries[FORGE_SEQ - 1]["hash"] if FORGE_SEQ else GENESIS_PREV
    for entry in entries[FORGE_SEQ:]:
        entry["prev"] = prev
        entry["hash"] = hash_of(
            {k: entry[k] for k in ("seq", "prev", "kind", "body", "spec")})
        prev = entry["hash"]

    with open(TARGET, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(canonical(entry).decode("utf-8") + "\n")
    print("wrote %s: %d entries, forged at seq %d, head %s"
          % (TARGET, len(entries), FORGE_SEQ, entries[-1]["hash"]))


if __name__ == "__main__":
    main()
