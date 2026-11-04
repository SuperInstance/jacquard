#!/usr/bin/env python3
"""Independent checks for the E7 joint battery.

Verifies, per split and across splits:
  1. JSONL validity (every line parses; required fields present/typed)
  2. class balance (120 per split, exactly 40 code / 40 mixed / 40 model)
  3. id sanity (format e7diag-NNN / e7held-NNN, unique, sequential)
  4. label-field sanity (label in {code, mixed, model}; subtype known;
     boundary is bool; message non-empty, sane length)
  5. no exact duplicate messages within or across splits
  6. no near-duplicate leakage across splits: normalised-text equality
     and token-set Jaccard similarity >= THRESHOLD on any cross-split
     pair (the maximum observed Jaccard is printed either way)
  7. split-field consistency (the split field matches the file)

Prints PASS/FAIL per check; exit 0 iff every check passes.
Stdlib only; runs anywhere.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {"code", "mixed", "model"}
EXPECTED_N = 120
EXPECTED_PER_CLASS = 40
JACCARD_THRESHOLD = 0.60
FILES = {"diagnostic": (HERE / "diagnostic.jsonl", "e7diag"),
         "heldout": (HERE / "heldout.jsonl", "e7held")}
KNOWN_SUBTYPES = {
    "plain_function", "diff", "stack_trace", "shell_log",
    "config_low_symbol", "prose_identifiers", "terse_code",
    "wordy_query", "reflective_status", "commit_prose",
    "design_note_code_dense", "chat_prose", "numbers_units_prose",
    "warm_narrative", "polysemy_prose", "terse_prose",
    "inline_code_quote", "code_long_comments", "warm_commit_dense",
    "error_shaped_prose", "prose_plus_log", "prose_plus_block",
}

results = []


def report(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: {name}"
          + (f" ({detail})" if detail else ""))


def normalise(text):
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def token_set(text):
    return set(normalise(text).split())


def load(split):
    path, _ = FILES[split]
    items, errors = [], []
    with path.open(encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            if not ln.strip():
                errors.append(f"{split}:{i} blank line")
                continue
            try:
                items.append(json.loads(ln))
            except ValueError as e:
                errors.append(f"{split}:{i} {e}")
    return items, errors


def main():
    all_items = {}
    valid = True
    for split in FILES:
        items, errors = load(split)
        all_items[split] = items
        if errors:
            valid = False
            report(f"{split} JSONL validity", False, "; ".join(errors[:3]))
        else:
            ok = all(
                isinstance(it.get("id"), str)
                and isinstance(it.get("split"), str)
                and isinstance(it.get("label"), str)
                and isinstance(it.get("subtype"), str)
                and isinstance(it.get("boundary"), bool)
                and isinstance(it.get("message"), str)
                for it in items)
            report(f"{split} JSONL validity + required fields", ok,
                   f"n={len(items)}")
            valid = valid and ok

    for split, (path, prefix) in FILES.items():
        items = all_items[split]
        counts = {lab: sum(1 for it in items if it.get("label") == lab)
                  for lab in sorted(LABELS)}
        report(f"{split} class balance",
               len(items) == EXPECTED_N
               and all(v == EXPECTED_PER_CLASS for v in counts.values()),
               f"n={len(items)} balance={counts}")
        ids = [it.get("id", "") for it in items]
        pat = re.compile(rf"^{prefix}-\d{{3}}$")
        seq = sorted(ids) == [f"{prefix}-{i:03d}"
                              for i in range(1, EXPECTED_N + 1)]
        report(f"{split} id format/uniqueness/sequence",
               len(set(ids)) == len(ids) and all(pat.match(x) for x in ids)
               and seq)
        report(f"{split} split-field consistency",
               all(it.get("split") == split for it in items))
        report(f"{split} label-field sanity",
               all(it.get("label") in LABELS
                   and it.get("subtype") in KNOWN_SUBTYPES
                   and isinstance(it.get("boundary"), bool)
                   and 3 <= len(it.get("message", "")) <= 4000
                   for it in items))

    diag = [it["message"] for it in all_items["diagnostic"]]
    held = [it["message"] for it in all_items["heldout"]]
    everything = diag + held
    report("no exact duplicate messages (within + across splits)",
           len(set(everything)) == len(everything),
           f"unique={len(set(everything))}/{len(everything)}")

    nd = [normalise(m) for m in diag]
    nh = [normalise(m) for m in held]
    report("no normalised-text duplicates across splits",
           not (set(nd) & set(nh)),
           f"overlap={len(set(nd) & set(nh))}")

    td = [token_set(m) for m in diag]
    th = [token_set(m) for m in held]
    worst, worst_pair = 0.0, None
    for i, a in enumerate(td):
        for j, b in enumerate(th):
            if not a or not b:
                continue
            jac = len(a & b) / len(a | b)
            if jac > worst:
                worst, worst_pair = jac, (i, j)
    report("no near-duplicate leakage across splits "
           f"(token Jaccard < {JACCARD_THRESHOLD})",
           worst < JACCARD_THRESHOLD,
           f"max cross-split Jaccard={worst:.3f} at diag#{worst_pair[0]}"
           f"/held#{worst_pair[1]}" if worst_pair else "no pairs")

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'}: "
          f"{sum(results)}/{len(results)} checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
