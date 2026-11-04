#!/usr/bin/env python3
"""Independent verification of the Phase 15 slice-43 round batteries.

Re-checks, WITHOUT importing gen_rounds.py or gen_batteries.py:
  * exact item counts: 60 items in each of the 6 round files
  * per-category balance in each round file: every one of the 8
    arithmetic categories has 7 or 8 items, totalling 60
  * every round item's split field, id prefix, category, and the
    prompt suffix "Answer with just the number."
  * every arithmetic derivation: parsed with a restricted AST
    walker (only + - * /, parentheses, numeric literals,
    max()/min() allowed), recomputed, and compared to the stored
    answer (exact for integers; |diff| <= 0.005 for money answers)
  * prompt uniqueness WITHIN each round file, ACROSS all round
    files, and AGAINST diagnostic / validation / heldout
  * derivation uniqueness likewise (within, across rounds, and
    against diagnostic / validation / heldout)
  * an independent prompt-parsing recompute: numbers and
    operations are extracted from the prompt TEXT by fresh regex
    logic written in this file (the derivation string is never
    used), the parsed answer must equal the stored answer for
    every parseable round item, and parse coverage must be
    >= 60% of round items
  * all word_2step gold answers are >= 0

Prints a PASS/FAIL summary, and also writes that same output to
batteries/rounds/VERIFY-ROUNDS.txt. Exit code 0 iff all checks
pass. Run:  python3 verify_rounds.py
"""
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROUNDS = [1, 2, 3, 4, 5, 6]
ROUND_FILES = {
    f"round{r}_diag": HERE / "batteries" / "rounds" / f"round{r}_diag.jsonl"
    for r in ROUNDS
}
BASE_FILES = {
    "diagnostic": HERE / "batteries" / "diagnostic.jsonl",
    "validation": HERE / "batteries" / "validation.jsonl",
    "heldout": HERE / "private" / "heldout.jsonl",
}
EXPECTED_PER_ROUND = 60
CATEGORIES = ["addsub_chain", "mul_2x1", "mul_2x2", "div_exact",
              "pct_of", "word_2step", "unit_price", "compare"]
END = "Answer with just the number."
OUT_PATH = HERE / "batteries" / "rounds" / "VERIFY-ROUNDS.txt"


# ---- independent prompt-parsing recompute ----
# Fresh regex logic, written for this verifier only (following the
# approach of verify_batteries.py's parser, re-written here). It
# reads ONLY the prompt text (plus the item category, to select
# the operation family) -- never the derivation string. The round
# batteries use template set A only, so the patterns below cover
# the set-A surface forms.

def _ints(text):
    return [int(x) for x in re.findall(r"\d+", text)]


def _parse_addsub(prompt):
    m = re.search(r"(\d+) \+ (\d+) - (\d+)", prompt)
    if m:
        a, b, c = (int(g) for g in m.groups()); return a + b - c
    m = re.search(r"had (\d+) .*bought (\d+) more and then gave away (\d+)", prompt)
    if m:
        a, b, c = (int(g) for g in m.groups()); return a + b - c
    m = re.search(r"stocked (\d+) .*sold (\d+) .*delivery of (\d+)", prompt)
    if m:
        a, c, b = (int(g) for g in m.groups()); return a - c + b
    return None


def _parse_pct(prompt):
    m = re.search(r"has (\d+) students and (\d+)% of them", prompt)
    if m:
        base, pct = int(m.group(1)), int(m.group(2))
        return base * pct / 100
    m = re.search(r"(\d+)% of (\d+)", prompt)
    if m:
        pct, base = int(m.group(1)), int(m.group(2))
        return base * pct / 100
    m = re.search(r"(\d+)(?:%| percent)\b", prompt)
    if m:
        pct = int(m.group(1))
        toks = [(int(t.group()), t.start())
                for t in re.finditer(r"\d+", prompt)]
        pct_idx = next((i for i, (_, st) in enumerate(toks)
                        if st == m.start(1)), None)
        for i, (n, _) in enumerate(toks):
            if i != pct_idx:
                return n * pct / 100
    return None


def _parse_word(prompt):
    m = re.search(r"buys (\d+) .* at (\d+) dollars each and pays with a (\d+) dollar bill", prompt)
    if m:
        a, price, note = (int(g) for g in m.groups()); return note - a * price
    m = re.search(r"reads (\d+) pages every day\. After (\d+) days, how many pages are left in a (\d+)-page book", prompt)
    if m:
        per, days, total = (int(g) for g in m.groups()); return total - per * days
    m = re.search(r"for (\d+) dollars each\. .* buys (\d+) on Monday and (\d+) on Tuesday", prompt)
    if m:
        price, a, b = (int(g) for g in m.groups()); return (a + b) * price
    return None


def _parse_unit(prompt):
    m = re.search(r"^(\d+) .* cost ([\d.]+) dollars in total", prompt)
    if m:
        return float(m.group(2)) / int(m.group(1))
    m = re.search(r"pays ([\d.]+) dollars for (\d+)", prompt)
    if m:
        return float(m.group(1)) / int(m.group(2))
    return None


def parse_prompt_answer(item):
    """Recompute the answer from the prompt text alone, or None."""
    prompt, cat = item["prompt"], item["category"]
    if cat == "addsub_chain":
        return _parse_addsub(prompt)
    if cat in ("mul_2x1", "mul_2x2"):
        nums = _ints(prompt)
        if len(nums) >= 2:
            return nums[0] * nums[1]
        return None
    if cat == "div_exact":
        nums = _ints(prompt)
        if len(nums) >= 2 and nums[1] != 0:
            return nums[0] / nums[1]
        return None
    if cat == "pct_of":
        return _parse_pct(prompt)
    if cat == "word_2step":
        return _parse_word(prompt)
    if cat == "unit_price":
        return _parse_unit(prompt)
    if cat == "compare":
        nums = _ints(prompt)
        return max(nums) if nums else None
    return None


failures = []
notes = []


def fail(msg):
    failures.append(msg)


def eval_derivation(expr):
    """Restricted AST evaluation of a derivation string."""
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.BinOp):
            l, r = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return l + r
            if isinstance(node.op, ast.Sub):
                return l - r
            if isinstance(node.op, ast.Mult):
                return l * r
            if isinstance(node.op, ast.Div):
                return l / r
            raise ValueError(f"operator {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op,
                                                        ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("max", "min"):
            fn = max if node.func.id == "max" else min
            return fn(ev(a) for a in node.args)
        raise ValueError(f"disallowed node {type(node).__name__}")

    return ev(tree)


def load(path):
    items = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def main():
    round_data = {}
    for name, path in ROUND_FILES.items():
        if not path.exists():
            fail(f"{name}: file missing: {path}")
            continue
        round_data[name] = load(path)
        if len(round_data[name]) != EXPECTED_PER_ROUND:
            fail(f"{name}: count {len(round_data[name])} != "
                 f"expected {EXPECTED_PER_ROUND}")
        else:
            notes.append(f"{name}: count {len(round_data[name])} OK")

    base_data = {}
    for name, path in BASE_FILES.items():
        if not path.exists():
            fail(f"base {name}: file missing: {path}")
            continue
        base_data[name] = load(path)
        notes.append(f"base {name}: {len(base_data[name])} items "
                     f"loaded for uniqueness checks")

    # per-round structure: split, category balance, suffix,
    # derivation recompute
    for r in ROUNDS:
        name = f"round{r}_diag"
        items = round_data.get(name, [])
        counts = Counter(it["category"] for it in items)
        for cat in CATEGORIES:
            if counts.get(cat, 0) not in (7, 8):
                fail(f"{name}/{cat}: {counts.get(cat, 0)} not in "
                     f"(7, 8)")
        if items:
            notes.append(f"{name}: category balance "
                         + ", ".join(f"{cat}={counts.get(cat, 0)}"
                                     for cat in CATEGORIES))
        for it in items:
            if it.get("split") != name:
                fail(f"{it.get('id')}: split field is "
                     f"{it.get('split')!r}, expected {name!r}")
            if it.get("category") not in CATEGORIES:
                fail(f"{it.get('id')}: unknown category "
                     f"{it.get('category')!r}")
            if not str(it.get("prompt", "")).endswith(END):
                fail(f"{it.get('id')}: prompt does not end with "
                     f"the required sentence")
            try:
                value = eval_derivation(it["derivation"])
            except Exception as e:  # noqa: BLE001
                fail(f"{it['id']}: derivation unparseable: {e}")
                continue
            gold = it["answer"]
            if isinstance(gold, int):
                if value != gold:
                    fail(f"{it['id']}: derivation gives {value}, "
                         f"stored answer {gold}")
            else:
                if abs(value - gold) > 0.005:
                    fail(f"{it['id']}: derivation gives {value}, "
                         f"stored answer {gold}")
            if it["category"] == "word_2step" and gold < 0:
                fail(f"{it['id']}: word_2step answer is negative "
                     f"({gold})")

    # prompt + derivation uniqueness: within each round file,
    # across all round files, and against the slice-41 files
    def check_unique(kind, keyfn, datasets, label):
        owner = {}
        dup = 0
        for ds_name, items in datasets:
            seen_here = set()
            for it in items:
                v = keyfn(it)
                if v is None:
                    continue
                if v in seen_here:
                    fail(f"{ds_name}: {kind} not unique within "
                         f"file: {str(v)[:60]!r}")
                    dup += 1
                seen_here.add(v)
                if v in owner and owner[v] != ds_name:
                    fail(f"{kind} shared between {owner[v]} and "
                         f"{ds_name}: {str(v)[:60]!r}")
                    dup += 1
                owner.setdefault(v, ds_name)
        if dup == 0:
            notes.append(f"{label}: OK")

    all_datasets = [(n, round_data.get(n, [])) for n in ROUND_FILES]
    all_datasets += [(n, base_data.get(n, [])) for n in BASE_FILES]
    check_unique("prompt", lambda it: it.get("prompt"),
                 all_datasets,
                 "prompt uniqueness (within-file, across rounds, "
                 "and against diagnostic/validation/heldout)")
    check_unique("derivation", lambda it: it.get("derivation"),
                 all_datasets,
                 "derivation uniqueness (within-file, across "
                 "rounds, and against diagnostic/validation/"
                 "heldout)")

    # independent prompt-parsing recompute over round items only
    parsed = 0
    total = 0
    for name, items in [(n, round_data.get(n, []))
                        for n in ROUND_FILES]:
        for it in items:
            total += 1
            try:
                pv = parse_prompt_answer(it)
            except Exception as e:  # noqa: BLE001
                fail(f"{it['id']}: prompt parser raised: {e}")
                continue
            if pv is None:
                continue
            parsed += 1
            if abs(float(pv) - float(it["answer"])) > 0.005:
                fail(f"{it['id']}: prompt-parsed answer {pv} != "
                     f"stored answer {it['answer']}")
    if total:
        cov = parsed / total
        notes.append(f"prompt-parse: {parsed}/{total} round items "
                     f"parsed ({cov:.1%} coverage)")
        if cov < 0.60:
            fail(f"prompt-parse coverage {cov:.1%} < 60% "
                 f"({parsed}/{total})")

    lines = ["=== round battery verification ==="]
    for n in notes:
        lines.append("  " + n)
    if failures:
        lines.append(f"FAIL ({len(failures)} problems)")
        for msg in failures[:50]:
            lines.append("  FAIL: " + msg)
        rc = 1
    else:
        lines.append("PASS: counts (60 x 6), category balance "
                     "(7-8 per category per round), derivation "
                     "recompute, prompt uniqueness and derivation "
                     "uniqueness (within-file, across all round "
                     "files, and against diagnostic/validation/"
                     "heldout), prompt-parse recompute, and "
                     "word_2step non-negativity all OK")
        rc = 0
    text = "\n".join(lines) + "\n"
    print(text, end="")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
