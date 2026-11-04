#!/usr/bin/env python3
"""W2 incumbent scorer — the gpu-queue spine's own rule, from the
record alone.

The incumbent behaviour for the job-shape joint is deterministic
and lives in the spine (Thor ~/gpu-queue/daemon.py): a feeder job
is materialised with its archetype chosen by rotation and written
into the job's name and cmd (`--archetype <label>`); a finite
foundry job arrives with the archetype in its cmd. The incumbent
"prediction" scored here is therefore the archetype parsed from
the item's own recorded text — the strongest possible statement
of what the incumbent does, and (see W2-BATTERY.md) the reason
the shadow bar is unreachable: gold and prediction are the same
recorded field, so this scorer is expected to be perfect, and
the harness exists to measure that, not to assert it.

Usage:
  python3 score_incumbent.py --battery diagnostic.jsonl [--out JSON]
  python3 score_incumbent.py --battery heldout.sealed.jsonl [--out JSON]
Stdlib only; no model, no GPU.
"""
import argparse, json, re, sys
from pathlib import Path

LABELS = ("fishing_boat", "harbor_house", "pier", "spruce")


def incumbent_predict(message):
    m = re.search(r"--archetype (\w+)", message or "")
    if m:
        return m.group(1)
    low = (message or "").lower()
    for lab in LABELS:  # name fallback, daemon's name template
        if lab in low:
            return lab
    return None


def summarise(records):
    per, conf = {}, {}
    for r in records:
        c = per.setdefault(r["gold"], [0, 0]); c[1] += 1; c[0] += 1 if r["correct"] else 0
        row = conf.setdefault(r["gold"], {})
        k = r["extracted"] or "none"; row[k] = row.get(k, 0) + 1
    n = len(records)
    return {"n": n, "accuracy": sum(r["correct"] for r in records) / n if n else 0.0,
            "per_class": {k: {"correct": v[0], "n": v[1], "accuracy": v[0] / v[1]}
                          for k, v in sorted(per.items())},
            "confusion": {k: dict(sorted(v.items())) for k, v in sorted(conf.items())}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--battery", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    items = [json.loads(l) for l in Path(a.battery).read_text().splitlines() if l.strip()]
    records = []
    for it in items:
        pred = incumbent_predict(it["message"])
        records.append({"id": it["id"], "gold": it["label"], "extracted": pred,
                        "correct": pred == it["label"]})
    split = items[0]["split"] if items else "unknown"
    res = summarise(records); res["items"] = records
    print(f"{split}: incumbent accuracy={res['accuracy']:.4f} (n={res['n']})")
    for lab, pc in res["per_class"].items():
        print(f"  {lab}: {pc['correct']}/{pc['n']} ({pc['accuracy']:.3f})")
    if a.out:
        Path(a.out).write_text(json.dumps({"scorer": "incumbent-parse-rule",
                                            "splits": {split: res}}, indent=1))
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
