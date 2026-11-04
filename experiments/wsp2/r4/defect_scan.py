#!/usr/bin/env python3
"""Quantifies the R4-INVENTORY defects over the shipped battery.

Imports ALARM / URGENCY from the real elephant panic.py (via
--elephant checkout root) so the lexicons scanned are the
incumbent's own, then counts over all battery messages:

 D1 substring traps: messages where a lexicon entry matches as
    a substring but NOT at a word boundary (multiword entries:
    boundaries required at both ends). Reported per entry.
 D3 flattening: messages where an ALARM/URGENCY entry occurs
    >= 2 times as a substring but the dial counts it once;
    "lost hits" = occurrences - 1 summed.
 D6 saturation context: distribution of room word counts (the
    alarm_norm denominator is max(word_count/40, 1)).

Output: JSON to --out (default stdout summary + file if given).
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def boundary_re(entry):
    return re.compile(r"(?<!\w)" + re.escape(entry) + r"(?!\w)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--elephant", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    sys.path.insert(0, str(Path(args.elephant).resolve()))
    from elephant.dials.panic import ALARM, URGENCY

    items = []
    for fn in ("diagnostic.jsonl", "validation.jsonl", "heldout.jsonl"):
        items += [json.loads(ln) for ln in
                  (HERE / fn).read_text(encoding="utf-8").splitlines()
                  if ln.strip()]
    trap = Counter()
    trap_msgs = 0
    lost = Counter()
    lost_total = 0
    word_counts = []
    n_msgs = 0
    for it in items:
        wc = 0
        for m in it["messages"]:
            n_msgs += 1
            text = m["text"].lower()
            wc += len(re.findall(r"\w+", text))
            msg_trapped = False
            for lex, name in ((ALARM, "ALARM"), (URGENCY, "URGENCY")):
                for entry in lex:
                    occ = text.count(entry)
                    if occ and not boundary_re(entry).search(text):
                        trap[f"{name}:{entry}"] += 1
                        msg_trapped = True
                    if occ >= 2:
                        lost[f"{name}:{entry}"] += occ - 1
                        lost_total += occ - 1
            trap_msgs += 1 if msg_trapped else 0
        word_counts.append(wc)
    word_counts.sort()
    res = {
        "n_items": len(items), "n_messages": n_msgs,
        "substring_trap_messages": trap_msgs,
        "substring_trap_by_entry": dict(trap.most_common()),
        "flattened_lost_hits": lost_total,
        "flattened_by_entry": dict(lost.most_common()),
        "room_word_count": {"min": word_counts[0],
                            "median": word_counts[len(word_counts) // 2],
                            "max": word_counts[-1],
                            "rooms_where_alarm_norm_denominator_is_1":
                                sum(1 for w in word_counts if w <= 40)},
    }
    print(json.dumps(res, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2),
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
