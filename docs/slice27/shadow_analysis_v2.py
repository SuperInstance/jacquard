#!/usr/bin/env python3
"""Phase 10 slice 27 — SHADOW consumption-policy v2 analysis.

Evidence only: nothing here changes live behaviour. Re-scores
the two live gpu-queue windows (docs/slice25/kernel.jsonl,
the same frozen log the v1 analysis scored) under the v2
semantics implemented in adapters/consumption.py — the same
code the bridge's consumption gate calls, so shadow and live
can never drift:

  v1 -> v2 changes (BUILD-BRIEF-PHASE10 slice 27):
  (1) the trailing ratio counts COMPLETED consumption only —
      a use counts when the consuming job's completion is
      recorded, never at its declaration (the bench-7
      promise-flattery fix);
  (2) the unbounded invisible cold-start exemption becomes
      an exemption BUDGET (3 completed outputs per producer)
      claimed as exemptions in the accounting below.

Scoring is strictly causal, exactly as v1: a submission is
priced only on log entries recorded before it; actual fates
are read from the whole log for classification only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "..", "adapters"))

from consumption import load_names, price_stream  # noqa: E402

JOB_CLASS = "gpu-bench"


def main(path):
    entries = [json.loads(l) for l in open(path)]
    names = load_names(entries, path + ".gpu-journal.jsonl")
    rows, claims = price_stream(entries, JOB_CLASS, names)
    print(json.dumps({"rows": rows,
                      "exemption_claims": claims}, indent=1))
    tp = sum(1 for r in rows
             if r["classification"].startswith("true-positive"))
    fp = sum(1 for r in rows
             if r["classification"] == "false-positive")
    ns = sum(1 for r in rows
             if r["classification"] == "no GPU time at stake")
    wh = sum(1 for r in rows if r["would_hold"])
    whr = sum(1 for r in rows if r["would_hold_refined"])
    print("SUMMARY v2 would_hold=%d refined=%d true_positive=%d "
          "false_positive=%d no_stake=%d exemption_claims=%s"
          % (wh, whr, tp, fp, ns, claims), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
