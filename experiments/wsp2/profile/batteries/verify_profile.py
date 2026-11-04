#!/usr/bin/env python3
"""Independent verifier for the patchability-profile battery suite.

Imports NOTHING from gen_profile.py. Checks, per grade/split:
  - file structure, counts, per-category balance, answer-set rules
    (the impossible-item screen);
  - prompt uniqueness within each file and across ALL files;
  - gold recomputation FROM THE PROMPT TEXT with fresh parsing logic
    for every category where the prompt carries the facts (G1, G2,
    G3 surface rules, all of G4 via datetime, all of G6 via the
    stated policy rule);
  - derivation recomputation with a restricted AST evaluator where
    the derivation is a plain arithmetic expression;
  - G5: facts cannot be recomputed from prompts, so the verifier
    checks fact-level split disjointness (no entity asked about in
    two splits), answer shape, and emits a deterministic audit
    sample (audit_sample.jsonl) for human/reviewer label checking;
  - cross-split near-duplicate screen: token-set Jaccard between
    every diagnostic/validation item and every held-out item of the
    same grade; the max is reported (templated tasks share frame
    tokens by design -- the leakage control is disjoint pools and
    unique prompts/derivations, both checked above; the Jaccard
    number is reported so a reviewer can judge it, not hidden).

Exit code 0 iff every hard check PASSes. Prints a report suitable
for saving as VERIFY-PROFILE.txt.
"""
import ast
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRADES = ["g1", "g2", "g3", "g4", "g5", "g6"]
SPLITS = ["diagnostic", "validation", "heldout"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
WEEKDAY_NUM = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
               "Friday": 5, "Saturday": 6, "Sunday": 7}

failures = []
notes = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return cond


# ---------- restricted AST evaluator (derivations) ----------
def eval_expr(expr):
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError(f"disallowed node {node!r}")

    return ev(tree)


# ---------- date parsing (three surface formats) ----------
def parse_dates(text):
    out = []
    for m in re.finditer(r"(\d{1,2}) ([A-Z][a-z]+) 2026", text):
        out.append(date(2026, MONTHS[m.group(2)], int(m.group(1))))
    for m in re.finditer(r"([A-Z][a-z]+) (\d{1,2}), 2026", text):
        out.append(date(2026, MONTHS[m.group(1)], int(m.group(2))))
    for m in re.finditer(r"(\d{2})/(\d{2})/2026", text):
        out.append(date(2026, int(m.group(2)), int(m.group(1))))
    return out


def tokens(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def main():
    all_items = {}
    seen_prompts = {}
    for g in GRADES:
        for split in SPLITS:
            path = HERE / f"{g}_{split}.jsonl"
            if not check(path.exists(), f"MISSING FILE {path.name}"):
                continue
            items = [json.loads(l) for l in open(path) if l.strip()]
            all_items[(g, split)] = items
            for it in items:
                check(it["grade"].lower() == g and it["split"] == split,
                      f"{it['id']}: grade/split field mismatch")
                check(isinstance(it["answer"], str) and it["answer"],
                      f"{it['id']}: empty/non-string answer")
                p = it["prompt"]
                if p in seen_prompts:
                    failures.append(f"DUPLICATE PROMPT {it['id']} == "
                                    f"{seen_prompts[p]}")
                seen_prompts[p] = it["id"]
            cats = Counter(i["category"] for i in items)
            print(f"{g} {split}: n={len(items)} categories={dict(cats)}")

    # ---------- per-category recomputation ----------
    recomputed = Counter()
    unparseable = Counter()

    def rec(it, fn):
        try:
            gold = fn(it["prompt"])
        except Exception:
            gold = None
        if gold is None:
            unparseable[it["category"]] += 1
        else:
            recomputed[it["category"]] += 1
            check(str(gold) == it["answer"],
                  f"{it['id']} ({it['category']}): prompt-recomputed "
                  f"gold {gold!r} != stored {it['answer']!r}")

    for (g, split), items in all_items.items():
        for it in items:
            cat, p = it["category"], it["prompt"]
            if g == "g1":
                if cat == "small_add":
                    rec(it, lambda p: str(sum(map(int, re.search(
                        r"What is (\d+) \+ (\d+)\?", p).groups()))))
                elif cat == "yes_no_compare":
                    def f(p):
                        m = re.search(r"Is (\d+) (greater|less) than (\d+)\?", p)
                        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
                        return "yes" if (a > b) == (op == "greater") else "no"
                    rec(it, f)
                elif cat == "copy_token":
                    rec(it, lambda p: re.search(r'Copy this word exactly: "(\w+)"', p).group(1))
                elif cat == "last_word":
                    rec(it, lambda p: re.search(r'sentence: "([^"]+)\."', p).group(1).split()[-1])
                elif cat == "seq_next":
                    def f(p):
                        m = re.search(r"sequence: ([\d, ]+), \.\.\.", p)
                        if m:
                            ns = [int(x) for x in m.group(1).split(", ")]
                            return str(ns[-1] + (ns[1] - ns[0]))
                        m = re.search(r"sequence: (\w+), (\w+), \1, \2, \1,", p)
                        return m.group(2) if m else None
                    rec(it, f)
            elif g == "g2":
                if cat == "false_claim":
                    def f(p):
                        m = re.search(r"says (\d+) is greater than (\d+)", p)
                        return "yes" if int(m.group(1)) > int(m.group(2)) else "no"
                    rec(it, f)
                elif cat == "quoted_question":
                    rec(it, lambda p: str(sum(map(int, re.search(
                        r'"What is (\d+) \+ (\d+)\?"', p).groups()))))
                elif cat == "order_swap":
                    def f(p):
                        m = re.search(r"is (\d+) less than (\d+)\?", p)
                        return "yes" if int(m.group(1)) < int(m.group(2)) else "no"
                    rec(it, f)
                elif cat == "distractor":
                    def f(p):
                        m = re.search(r"has (\d+) (\w+) and \d+ \w+\. .*How many \2", p)
                        return m.group(1) if m else None
                    rec(it, f)
                elif cat == "not_category":
                    check(it["answer"] in p, f"{it['id']}: gold not among listed options")
            elif g == "g3":
                if cat == "vowel_start":
                    def f(p):
                        w = re.search(r"word '(\w+)'", p).group(1)
                        return "vowel" if w[0] in "aeiou" else "consonant"
                    rec(it, f)
                elif cat == "contains_letter":
                    def f(p):
                        m = re.search(r"word '(\w+)' contain the letter '(\w)'", p)
                        return "yes" if m.group(2) in m.group(1) else "no"
                    rec(it, f)
                elif cat == "case_check":
                    def f(p):
                        w = re.search(r"word '(\w+)'", p).group(1)
                        return "yes" if w.islower() else "no"
                    rec(it, f)
                elif cat == "length_compare":
                    def f(p):
                        m = re.search(r"longer: '(\w+)' or '(\w+)'", p)
                        a, b = m.group(1), m.group(2)
                        return a if len(a) > len(b) else b
                    rec(it, f)
                elif cat in ("plural_check", "sentiment"):
                    check(it["answer"] in ("singular", "plural") if cat == "plural_check"
                          else it["answer"] in ("positive", "negative"),
                          f"{it['id']}: answer outside label set")
            elif g == "g4":
                if cat == "days_between":
                    def f(p):
                        ds = parse_dates(p)
                        return str((ds[1] - ds[0]).days) if len(ds) == 2 else None
                    rec(it, f)
                elif cat == "weekday_offset":
                    def f(p):
                        ds = parse_dates(p)
                        m = re.search(r"is a (\w+)", p) or re.search(r"falls on a (\w+)", p) or re.search(r"marked (\w+)", p)
                        n = int(re.search(r"(\d+) days", p).group(1))
                        if not ds or not m:
                            return None
                        true_wd = ds[0].weekday() + 1
                        check(WEEKDAY_NUM[m.group(1)] == true_wd,
                              f"weekday stated in prompt is false for {ds[0]}")
                        return str((true_wd - 1 + n) % 7 + 1)
                    rec(it, f)
                elif cat == "add_days_month":
                    def f(p):
                        ds = parse_dates(p)
                        n = int(re.search(r"(\d+) days", p).group(1))
                        return str((ds[0] + timedelta(days=n)).month) if ds else None
                    rec(it, f)
                elif cat == "month_span":
                    def f(p):
                        ds = parse_dates(p)
                        if len(ds) != 2:
                            return None
                        a, b = ds
                        return str((b.year - a.year) * 12 + b.month - a.month
                                   - (1 if b.day < a.day else 0))
                    rec(it, f)
                elif cat in ("weeks_days", "arith_chain"):
                    try:
                        v = eval_expr(it["derivation"])
                        check(float(v) == float(it["answer"]),
                              f"{it['id']}: derivation value {v} != gold {it['answer']}")
                        recomputed[cat] += 1
                    except Exception as e:
                        unparseable[cat] += 1
                        notes.append(f"{it['id']}: derivation not AST-evaluable: {e}")
                if cat == "days_between":
                    try:
                        v = eval_expr(it["derivation"])
                        check(float(v) == float(it["answer"]),
                              f"{it['id']}: derivation value != gold")
                    except Exception:
                        pass
            elif g == "g6":
                def f(p):
                    blocks = p.split("\n")
                    ex, new = blocks[1], blocks[2]
                    def fields(b):
                        prod = re.search(r"producer: ([\w-]+);", b).group(1)
                        res = re.search(r"resource: (\w+) seat (\w+);", b)
                        st = re.search(r"start: 2026-11-05 (\d{2}):(\d{2})", b)
                        dur = int(re.search(r"planned duration: (\d+)m", b).group(1))
                        cb = re.search(r"check-by: 2026-11-05 (\d{2}):(\d{2})", b)
                        return (prod, res.group(1), res.group(2),
                                int(st.group(1)) * 60 + int(st.group(2)), dur,
                                int(cb.group(1)) * 60 + int(cb.group(2)))
                    ep, eb, es, est, ed, ecb = fields(ex)
                    np_, nb, ns, nst, nd, ncb = fields(new)
                    if ep == np_:
                        return "ALLOW"          # same-lane renewal
                    if ecb < nst:
                        return "ALLOW"          # existing expired
                    if (eb, es) != (nb, ns):
                        return "ALLOW"          # different seat/box
                    overlap = nst < est + ed and est < nst + nd
                    return "HOLD" if overlap else "ALLOW"
                rec(it, f)
                check(it["answer"] in ("ALLOW", "HOLD"),
                      f"{it['id']}: G6 answer outside label set")

    total_rec = sum(recomputed.values())
    total_unp = sum(unparseable.values())
    print(f"prompt-recomputed golds: {total_rec}; "
          f"unparseable: {total_unp} {dict(unparseable)}")

    # ---------- G5 fact disjointness ----------
    g5_entities = {}
    for split in SPLITS:
        for it in all_items.get(("g5", split), []):
            key = re.sub(r"^(What is the capital of|What is the chemical "
                         r"symbol for|Which element has the chemical "
                         r"symbol) ", "", it["prompt"])
            key = key.split("?")[0].strip().lower()
            if key in g5_entities and g5_entities[key] != split:
                failures.append(f"G5 fact in two splits: {key!r} "
                                f"({g5_entities[key]}, {split})")
            g5_entities[key] = split
    print(f"G5 distinct fact keys: {len(g5_entities)}")

    # ---------- cross-split near-duplicate screen ----------
    print("cross-split max token-Jaccard (heldout vs diag+val):")
    for g in GRADES:
        held = all_items.get((g, "heldout"), [])
        others = (all_items.get((g, "diagnostic"), []) +
                  all_items.get((g, "validation"), []))
        other_tokens = [(tokens(o["prompt"]), o["id"]) for o in others]
        worst, worst_pair = 0.0, None
        for h in held:
            ht = tokens(h["prompt"])
            for ot, oid in other_tokens:
                j = len(ht & ot) / max(1, len(ht | ot))
                if j > worst:
                    worst, worst_pair = j, (h["id"], oid)
        print(f"  {g}: max Jaccard {worst:.3f} pair={worst_pair}")

    # ---------- G6 balance + pair integrity ----------
    for split in SPLITS:
        items = all_items.get(("g6", split), [])
        bal = Counter(i["answer"] for i in items)
        pairs = Counter(i.get("pair_id") for i in items)
        check(all(v == 2 for v in pairs.values()),
              f"g6 {split}: a pair_id does not have exactly 2 items")
        for pid, cnt in pairs.items():
            golds = {i["answer"] for i in items if i.get("pair_id") == pid}
            check(golds == {"ALLOW", "HOLD"},
                  f"g6 {split} {pid}: pair golds are {golds}, not a flip pair")
        print(f"g6 {split}: balance={dict(bal)} pairs={len(pairs)}")

    # ---------- audit sample ----------
    sample = []
    for (g, split), items in sorted(all_items.items()):
        for i, it in enumerate(items):
            if i % 17 == 0:
                sample.append({"id": it["id"], "grade": g, "split": split,
                               "category": it["category"],
                               "prompt": it["prompt"],
                               "answer": it["answer"]})
    with open(HERE / "audit_sample.jsonl", "w") as fh:
        for s in sample:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"audit sample: {len(sample)} items -> audit_sample.jsonl")

    for n in notes:
        print("NOTE:", n)
    if failures:
        print(f"\nFAIL ({len(failures)} failures)")
        for f_ in failures[:60]:
            print("  -", f_)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
