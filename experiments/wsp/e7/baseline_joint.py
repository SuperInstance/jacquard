#!/usr/bin/env python3
"""Spine+joint baseline: run signal_chain_dial._score over both splits.

The dial returns a continuous balance in [-1, +1] (-1 = pure code,
+1 = pure model). It is mapped to the battery's 3 classes by equal
thirds of the dial's own range:

  balance <= -1/3  ->  code
  -1/3 < balance < +1/3  ->  mixed
  balance >= +1/3  ->  model

Equal thirds is the simplest stated mapping that uses no battery
information (no threshold was tuned on these items). Note the dial
returns exactly 0.0 both for genuinely balanced text and for text
with no lexicon/symbol signal at all; both land in `mixed` here.

Imports _score read-only from ~/sigchain-read. Stdlib only.
Usage: python3 baseline_joint.py [--json OUT]
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAL_PATH = Path.home() / "sigchain-read" / "signal_chain_dial.py"
THIRD = 1.0 / 3.0


def to_class(balance):
    if balance <= -THIRD:
        return "code"
    if balance >= THIRD:
        return "model"
    return "mixed"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="also write full results JSON here")
    args = ap.parse_args()

    spec = importlib.util.spec_from_file_location("dial", DIAL_PATH)
    dial = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dial)

    result = {"thresholds": {"code_max": -THIRD, "model_min": THIRD},
              "splits": {}}
    for split in ("diagnostic", "heldout"):
        items = [json.loads(ln) for ln in
                 (HERE / f"{split}.jsonl").open(encoding="utf-8")
                 if ln.strip()]
        records, confusion, per_sub = [], {}, {}
        for it in items:
            text = it["message"].lower()
            words = dial.WORD_RE.findall(text)
            bal = dial._score(text, words)
            pred = to_class(bal)
            ok = pred == it["label"]
            records.append({"id": it["id"], "gold": it["label"],
                            "subtype": it["subtype"],
                            "boundary": it["boundary"],
                            "dial_score": round(bal, 4),
                            "predicted": pred, "correct": ok})
            row = confusion.setdefault(it["label"], {})
            row[pred] = row.get(pred, 0) + 1
            s = per_sub.setdefault(it["subtype"], [0, 0])
            s[1] += 1
            s[0] += 1 if ok else 0
        n = len(records)
        acc = sum(r["correct"] for r in records) / n
        per_class = {}
        for lab in ("code", "mixed", "model"):
            sub = [r for r in records if r["gold"] == lab]
            per_class[lab] = {"correct": sum(r["correct"] for r in sub),
                              "n": len(sub),
                              "accuracy": sum(r["correct"] for r in sub)
                              / len(sub)}
        bnd = [r for r in records if r["boundary"]]
        plain = [r for r in records if not r["boundary"]]
        result["splits"][split] = {
            "n": n, "accuracy": acc, "per_class": per_class,
            "confusion": confusion,
            "boundary_accuracy": sum(r["correct"] for r in bnd)
            / len(bnd),
            "nonboundary_accuracy": sum(r["correct"] for r in plain)
            / len(plain),
            "per_subtype": {k: {"correct": v[0], "n": v[1],
                                "accuracy": v[0] / v[1]}
                            for k, v in sorted(per_sub.items())},
            "items": records}
        print(f"== {split}: accuracy {acc:.4f} (n={n})")
        for lab, pc in per_class.items():
            print(f"   {lab}: {pc['correct']}/{pc['n']} "
                  f"({pc['accuracy']:.3f})")
        print(f"   confusion gold->pred: {json.dumps(confusion)}")
        print(f"   boundary items: "
              f"{result['splits'][split]['boundary_accuracy']:.3f} | "
              f"non-boundary: "
              f"{result['splits'][split]['nonboundary_accuracy']:.3f}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2),
                                   encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
