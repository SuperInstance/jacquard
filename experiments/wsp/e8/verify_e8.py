#!/usr/bin/env python3
"""Independent checks for the E8 decision battery.

Run on the Oracle:  python3 verify_e8.py [--dir PATH]
Reads diagnostic.jsonl and heldout.jsonl (default: beside this
script), prints PASS/FAIL per check, exits nonzero on any FAIL.

Checks:
  1. JSONL validity — every line parses as a JSON object with
     the required fields.
  2. Disjoint splits — no item id, and no (source, source_pointer
     locator) pair, appears in both splits; no duplicate ids
     within a split.
  3. Gold labels — every gold and every non-null correct_outcome
     is in {ALLOW, HOLD, DENY}.
  4. Source pointers — every item carries source_pointer.file
     and .locator, non-empty, so it can be audited back to the
     record.
  5. Time split — every diagnostic item's order_ts is before
     the boundary 2026-11-03T00:00:00Z and every held-out item's
     is at/after it.
  6. Correctness consistency — operator_correct false implies
     correct_outcome present and different from gold;
     operator_correct true implies correct_outcome == gold;
     operator_correct null implies correct_outcome null.
  7. Leakage scan — two tiers:
     HARD (fail): verdict-phrase patterns that state an outcome
     as something that happened to this item, e.g. "was allowed",
     "decision: deny", "released by", "outcome:".
     SOFT (report only): any outcome-lexicon token in a context.
     The lexicon: allow/allowed/allows, hold/held, deny/denied/
     denies, queue/queued, release/released, reject/rejected,
     approve/approved, refused/refusal. Soft hits are EXPECTED
     in known neutral classes — the resource name "job-queue",
     stated policy rules in jev policy-case texts, lane-written
     booking task text — so they are enumerated per item as
     borderline cases for a human/coordinator to judge, never
     silently passed over.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BOUNDARY = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
LABELS = {"ALLOW", "HOLD", "DENY"}
REQUIRED = {"id", "split", "source", "order_ts", "ts_basis",
            "context", "gold", "operator_correct",
            "correct_outcome", "correctness_evidence",
            "source_pointer"}
LEXICON = {"allow", "allowed", "allows", "hold", "held", "deny",
           "denied", "denies", "queue", "queued", "release",
           "released", "reject", "rejected", "approve",
           "approved", "refused", "refusal"}
HARD_PATTERNS = [
    r"\bwas (allowed|denied|held|queued|released|rejected|approved)\b",
    r"\bwere (allowed|denied|held|queued|released|rejected|approved)\b",
    r"\bhas been (allowed|denied|held|queued|released|rejected)\b",
    r"\boutcome\s*[:=]",
    r"\bdecision\s*[:=]\s*(allow|hold|deny)\b",
    r"\bverdict\s*[:=]",
    r"\b(released|rejected|approved) by\b",
    r"\bgold\s*[:=]",
]


def load(path):
    items, bad = [], []
    for ln, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except ValueError as e:
            bad.append((ln, str(e)))
    return items, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=str(Path(__file__).resolve()
                                         .parent))
    args = ap.parse_args()
    base = Path(args.dir)
    results = []

    def report(name, ok, detail=""):
        results.append(ok)
        print("%s: %s%s" % ("PASS" if ok else "FAIL", name,
                            (" — " + detail) if detail else ""))

    diag, bad_d = load(base / "diagnostic.jsonl")
    held, bad_h = load(base / "heldout.jsonl")

    # 1. JSONL validity + fields + split field matches file
    ok = not bad_d and not bad_h
    detail = ""
    if bad_d or bad_h:
        detail = "unparseable lines: diag %s held %s" % (bad_d, bad_h)
    for split_name, rows in (("diagnostic", diag), ("heldout", held)):
        for it in rows:
            missing = REQUIRED - set(it)
            if missing:
                ok = False
                detail += " %s missing %s;" % (it.get("id"), missing)
            if it.get("split") != split_name:
                ok = False
                detail += " %s split field %r in %s file;" % (
                    it.get("id"), it.get("split"), split_name)
            if not isinstance(it.get("context"), str) \
                    or not it["context"].strip():
                ok = False
                detail += " %s empty context;" % it.get("id")
    report("jsonl-validity", ok, detail or
           "%d diagnostic + %d heldout items parse" % (len(diag),
                                                       len(held)))

    # 2. disjoint
    ids_d = [i["id"] for i in diag]
    ids_h = [i["id"] for i in held]
    ptr = lambda i: (i["source"], i["source_pointer"]["locator"])
    overlap_ids = set(ids_d) & set(ids_h)
    overlap_ptr = {ptr(i) for i in diag} & {ptr(i) for i in held}
    dup = len(ids_d) != len(set(ids_d)) or \
        len(ids_h) != len(set(ids_h))
    report("disjoint-splits", not overlap_ids and not overlap_ptr
           and not dup,
           "id overlap %s; pointer overlap %d; intra-split dup %s"
           % (sorted(overlap_ids), len(overlap_ptr), dup)
           if (overlap_ids or overlap_ptr or dup) else
           "no id or source-pointer overlap; ids unique per split")

    # 3. gold labels
    bad_labels = [(i["id"], i["gold"]) for i in diag + held
                  if i["gold"] not in LABELS]
    bad_co = [(i["id"], i["correct_outcome"]) for i in diag + held
              if i["correct_outcome"] is not None
              and i["correct_outcome"] not in LABELS]
    report("gold-labels", not bad_labels and not bad_co,
           "bad gold %s; bad correct_outcome %s" % (bad_labels,
                                                    bad_co)
           if (bad_labels or bad_co) else
           "all golds and correct_outcomes in {ALLOW,HOLD,DENY}")

    # 4. source pointers
    bad_ptr = [i["id"] for i in diag + held
               if not (i["source_pointer"].get("file") and
                       i["source_pointer"].get("locator"))]
    report("source-pointers", not bad_ptr,
           "missing/empty pointers: %s" % bad_ptr if bad_ptr else
           "every item carries file + locator")

    # 5. time split
    def ts(i):
        return datetime.fromisoformat(i["order_ts"])
    bad_time = [i["id"] for i in diag if ts(i) >= BOUNDARY] + \
               [i["id"] for i in held if ts(i) < BOUNDARY]
    report("time-split", not bad_time,
           "items on the wrong side of 2026-11-03T00:00:00Z: %s"
           % bad_time if bad_time else
           "all diagnostic < boundary <= all heldout")

    # 6. correctness consistency
    bad_c = []
    for i in diag + held:
        oc, co, g = i["operator_correct"], i["correct_outcome"], \
            i["gold"]
        if oc is False and not (co in LABELS and co != g):
            bad_c.append((i["id"], "false but correct_outcome=%r"
                          % co))
        if oc is True and co != g:
            bad_c.append((i["id"], "true but correct_outcome=%r "
                          "!= gold" % co))
        if oc is None and co is not None:
            bad_c.append((i["id"], "null but correct_outcome=%r"
                          % co))
        if oc is not None and oc not in (True, False):
            bad_c.append((i["id"], "operator_correct=%r" % oc))
    report("correctness-consistency", not bad_c,
           "; ".join("%s %s" % x for x in bad_c) if bad_c else
           "false=>corrected outcome differs; true=>equals gold; "
           "null=>no correct_outcome")

    # 7. leakage
    hard_hits = []
    soft = []
    for i in diag + held:
        low = i["context"].lower()
        for pat in HARD_PATTERNS:
            if re.search(pat, low):
                hard_hits.append((i["id"], pat))
        toks = set(re.findall(r"[a-z]+", low)) & LEXICON
        if toks:
            soft.append((i["id"], i["split"], sorted(toks)))
    report("leakage-hard", not hard_hits,
           "verdict-phrase hits: %s" % hard_hits if hard_hits else
           "no verdict-phrase pattern in any context")
    print("leakage-soft (borderline, reported not failed): "
          "%d items with outcome-lexicon tokens" % len(soft))
    for item_id, split, toks in soft:
        print("  soft: %s [%s] tokens=%s" % (item_id, split,
                                             ",".join(toks)))
    print("leakage-soft note: 'queue' hits are dominated by the "
          "resource name job-queue/gpu job-queue and queue-state "
          "descriptions; 'denied' hits in jev items are stated "
          "policy rules from the source text. Each listed item is "
          "a borderline case for the coordinator to judge.")

    print("VERIFY %s (%d/%d checks passed)"
          % ("PASS" if all(results) else "FAIL",
             sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
