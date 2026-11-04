#!/usr/bin/env python3
"""Independent verification of the Phase 15 batteries.

Re-checks, WITHOUT importing gen_batteries.py:
  * exact item counts per file
  * every arithmetic derivation: parsed with an AST walker (only
    + - * /, parentheses, numeric literals, max()/min() allowed),
    recomputed, and compared to the stored answer
    (exact for integers; |diff| <= 0.005 for money answers)
  * per-category counts in the arithmetic splits
  * every arithmetic prompt ends with "Answer with just the number."
  * no prompt string appears in more than one split (all six files)
  * no heldout prompt contains any set-A-only marker phrase
  * forget_instr check objects are well-formed; forget_fact items
    have non-empty answers; forget_prose paragraphs are 60-90 words

Prints a PASS/FAIL summary. Exit code 0 iff all checks pass.
Run:  python3 verify_batteries.py
"""
import ast
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "diagnostic": (HERE / "batteries" / "diagnostic.jsonl", 80),
    "validation": (HERE / "batteries" / "validation.jsonl", 200),
    "heldout": (HERE / "private" / "heldout.jsonl", 200),
    "forget_instr": (HERE / "private" / "forget_instr.jsonl", 100),
    "forget_fact": (HERE / "private" / "forget_fact.jsonl", 100),
    "forget_prose": (HERE / "private" / "forget_prose.jsonl", 24),
}
ARITH_SPLITS = ["diagnostic", "validation", "heldout"]
CATEGORIES = ["addsub_chain", "mul_2x1", "mul_2x2", "div_exact",
              "pct_of", "word_2step", "unit_price", "compare"]
END = "Answer with just the number."

# Phrases that appear only in template set A / lexical pool A.
SET_A_MARKERS = ["Compute:", "What is", "Multiply", "Divide",
                 "corner shop", "market stall", "school store",
                 "% of", "packs of", "in each pack", "rows of chairs",
                 "Maya", "Liam", "Sofia", "Noah", "Ava", "Ethan",
                 "Mia", "Lucas", "marbles", "stickers", "pencils",
                 "apples", "trading cards", "shells", "buttons"]

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
    data = {}
    for name, (path, expected) in FILES.items():
        if not path.exists():
            fail(f"{name}: file missing: {path}")
            continue
        data[name] = load(path)
        if len(data[name]) != expected:
            fail(f"{name}: count {len(data[name])} != expected {expected}")
        else:
            notes.append(f"{name}: count {len(data[name])} OK")

    # arithmetic derivations, categories, suffix
    for split in ARITH_SPLITS:
        items = data.get(split, [])
        counts = Counter(it["category"] for it in items)
        per = 10 if split == "diagnostic" else 25
        for cat in CATEGORIES:
            if counts.get(cat, 0) != per:
                fail(f"{split}/{cat}: {counts.get(cat, 0)} != {per}")
        for it in items:
            if it.get("split") != split:
                fail(f"{it['id']}: split field is {it.get('split')!r}")
            if not it["prompt"].endswith(END):
                fail(f"{it['id']}: prompt does not end with the "
                     f"required sentence")
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

    # prompt uniqueness across ALL files
    owner = {}
    for name, items in data.items():
        for it in items:
            p = it.get("prompt") or it.get("text")
            if p in owner and owner[p] != name:
                fail(f"prompt shared between {owner[p]} and {name}: "
                     f"{p[:60]!r}")
            owner.setdefault(p, name)

    # heldout must carry no set-A marker
    for it in data.get("heldout", []):
        for marker in SET_A_MARKERS:
            if marker in it["prompt"]:
                fail(f"{it['id']}: heldout prompt contains set-A "
                     f"marker {marker!r}")

    # forget_instr structure
    valid_checks = {"json_key", "all_caps", "starts_with", "ends_with",
                    "bullets3", "word_count_range"}
    for it in data.get("forget_instr", []):
        chk = it.get("check", {})
        t = chk.get("type")
        if t not in valid_checks:
            fail(f"{it['id']}: unknown check type {t!r}")
        elif t == "json_key" and not chk.get("key"):
            fail(f"{it['id']}: json_key check missing key")
        elif t in ("starts_with", "ends_with") and not chk.get("word"):
            fail(f"{it['id']}: {t} check missing word")
        elif t == "word_count_range" and not (
                0 < chk.get("lo", 0) < chk.get("hi", 0)):
            fail(f"{it['id']}: bad word_count_range {chk}")

    # forget_fact structure
    fcounts = Counter(it["category"]
                      for it in data.get("forget_fact", []))
    for cat, want in [("capitals", 30), ("elements", 25),
                      ("solar_system", 15), ("conversions", 15),
                      ("misc", 15)]:
        if fcounts.get(cat, 0) != want:
            fail(f"forget_fact/{cat}: {fcounts.get(cat, 0)} != {want}")
    for it in data.get("forget_fact", []):
        if not str(it.get("answer", "")).strip():
            fail(f"{it['id']}: empty answer")
        if not isinstance(it.get("aliases"), list):
            fail(f"{it['id']}: aliases is not a list")

    # forget_prose structure
    for it in data.get("forget_prose", []):
        wc = len(it["text"].split())
        if not (60 <= wc <= 90):
            fail(f"{it['id']}: prose word count {wc} outside 60-90")

    print("=== battery verification ===")
    for n in notes:
        print("  " + n)
    if failures:
        print(f"FAIL ({len(failures)} problems)")
        for msg in failures[:50]:
            print("  FAIL: " + msg)
        return 1
    print("PASS: counts, derivations, category balance, prompt "
          "uniqueness, heldout marker hygiene, and structural checks "
          "all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
