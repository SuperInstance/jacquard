"""Generate signature-expectations.json — the Python side of the
section 12.1 shape-signature comparison (slice 19).

For each proof-run corpus, every decision entry that records a
request list (the queued population the signature discriminates,
spec 12.1) contributes one item: its seq, its proposal_id, and
the signature the PYTHON learner computes for its requests.
check.ts recomputes every signature with the TypeScript port
and compares item-for-item, plus the canonical hash of each
corpus's item list. Regenerate with:

    python3 conformance/ts/gen_signature_expectations.py
"""
import hashlib
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from jacquard.canonical import canonical  # noqa: E402
from jacquard.learner import shape_signature  # noqa: E402

CORPORA = ["docs/proof-run/kernel.jsonl", "docs/proof-run-2/kernel.jsonl"]


def corpus_items(relpath):
    items = []
    with open(os.path.join(ROOT, relpath), "r", encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    for entry in entries:
        body = entry["body"]
        if entry["kind"] == "decision" and "requests" in body:
            items.append({
                "seq": entry["seq"],
                "proposal_id": body.get("proposal_id"),
                "signature": shape_signature(body["requests"]),
            })
    digest = hashlib.sha256(canonical(items)).hexdigest()
    return {"path": relpath, "entry_count": len(entries),
            "items": items, "items_hash": digest}


def main():
    out = {"corpora": [corpus_items(p) for p in CORPORA]}
    path = os.path.join(os.path.dirname(__file__),
                        "signature-expectations.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for corpus in out["corpora"]:
        print(corpus["path"], len(corpus["items"]), corpus["items_hash"])


if __name__ == "__main__":
    main()
