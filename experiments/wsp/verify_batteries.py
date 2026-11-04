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
  * no prompt string appears in more than one split (all six files),
    and prompts are unique WITHIN each file too (N2)
  * no heldout prompt contains any marker from the generator-emitted
    batteries/setA_markers.json (N3: all pool-A strings + set-A
    template frame fragments)
  * an independent prompt-parsing recompute (N1): numbers and
    operations are extracted from the prompt TEXT by fresh regex
    logic here (the derivation string is never used), the parsed
    answer must equal the stored answer for every parseable item,
    and parse coverage must be >= 60% of arithmetic items
  * all word_2step gold answers are >= 0 (F4)
  * bare-symbolic-form share of each arithmetic split is in the
    25-35% band (F2c)
  * forget_instr check objects are well-formed; forget_fact items
    have non-empty answers; forget_prose paragraphs are 60-90 words

Prints a PASS/FAIL summary. Exit code 0 iff all checks pass.
Run:  python3 verify_batteries.py
"""
import ast
import json
import re
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

# N3: markers are NOT a hand list here. The generator emits
# batteries/setA_markers.json containing ALL pool-A strings plus
# set-A template frame fragments; load_markers() reads it.
MARKERS_PATH = HERE / "batteries" / "setA_markers.json"


def load_markers():
    if not MARKERS_PATH.exists():
        fail(f"setA markers file missing: {MARKERS_PATH}")
        return []
    try:
        data = json.loads(MARKERS_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fail(f"setA markers file unparseable: {e}")
        return []
    if isinstance(data, dict) and isinstance(data.get("markers"), list):
        return [str(m) for m in data["markers"]]
    if isinstance(data, list):
        return [str(m) for m in data]
    fail("setA markers file has no 'markers' list")
    return []


# ---- bare-form classifier (F2c) ----
# A bare symbolic form is a short prompt that states the arithmetic
# symbolically / in operator words, with no narrative story.
_BARE_RES = [
    re.compile(r"^Compute:"),
    re.compile(r"^Calculate:"),
    re.compile(r"^What is "),
    re.compile(r"^Multiply "),
    re.compile(r"^Divide "),
    re.compile(r"^Work out \d+ lots of "),
    re.compile(r"^\d+ \* \d+ equals what\?"),
    re.compile(r"^\d+ / \d+ equals what\?"),
    re.compile(r"^\d+ percent of \d+ equals what\?"),
]


def is_bare(prompt):
    return any(rx.search(prompt) for rx in _BARE_RES)


# ---- N1: independent prompt-parsing recompute ----
# Fresh regex logic, written for the verifier only. It reads ONLY
# the prompt text (plus the item category, to select the operation
# family) -- never the derivation string.

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
    m = re.search(r"Beginning from (\d+), increase by (\d+), then decrease by (\d+)", prompt)
    if m:
        a, b, c = (int(g) for g in m.groups()); return a + b - c
    m = re.search(r"jar held (\d+) .*dropped in (\d+) more.*took out (\d+)", prompt)
    if m:
        a, b, c = (int(g) for g in m.groups()); return a + b - c
    return None


def _parse_pct(prompt):
    m = re.search(r"(\d+) percent of (\d+)", prompt)
    if m:
        pct, base = int(m.group(1)), int(m.group(2))
        return base * pct / 100
    m = re.search(r"(\d+)% of (\d+)", prompt)
    if m:
        pct, base = int(m.group(1)), int(m.group(2))
        return base * pct / 100
    # percent named second: the base is the integer token that is
    # not the percent token (identified by token position, so this
    # works even when base == pct numerically)
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
    m = re.search(r"hands over a (\d+) dollar note for (\d+) .* costing (\d+) dollars apiece", prompt)
    if m:
        note, a, price = (int(g) for g in m.groups()); return note - a * price
    m = re.search(r"reads (\d+) pages every day\. After (\d+) days, how many pages are left in a (\d+)-page book", prompt)
    if m:
        per, days, total = (int(g) for g in m.groups()); return total - per * days
    m = re.search(r"works through a (\d+)-page novel at (\d+) pages daily\. Once (\d+) days have passed", prompt)
    if m:
        total, per, days = (int(g) for g in m.groups()); return total - per * days
    m = re.search(r"for (\d+) dollars each\. .* buys (\d+) on Monday and (\d+) on Tuesday", prompt)
    if m:
        price, a, b = (int(g) for g in m.groups()); return (a + b) * price
    m = re.search(r"priced at (\d+) dollars apiece\. .* picks up (\d+) on Friday and (\d+) on Saturday", prompt)
    if m:
        price, a, b = (int(g) for g in m.groups()); return (a + b) * price
    m = re.search(r"crate holds (\d+) .* fills (\d+) crates, then sells (\d+)", prompt)
    if m:
        per, crates, sold = (int(g) for g in m.groups()); return crates * per - sold
    m = re.search(r"saves (\d+) dollars a week for (\d+) weeks, then spends (\d+)", prompt)
    if m:
        per, weeks, spent = (int(g) for g in m.groups()); return weeks * per - spent
    return None


def _parse_unit(prompt):
    m = re.search(r"^(\d+) .* cost ([\d.]+) dollars in total", prompt)
    if m:
        return float(m.group(2)) / int(m.group(1))
    m = re.search(r"pays ([\d.]+) dollars for (\d+)", prompt)
    if m:
        return float(m.group(1)) / int(m.group(2))
    m = re.search(r"set of (\d+) .* priced at ([\d.]+) dollars", prompt)
    if m:
        return float(m.group(2)) / int(m.group(1))
    m = re.search(r"For ([\d.]+) dollars, .* bought (\d+)", prompt)
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

    # F4: no word_2step gold may be negative
    for split in ARITH_SPLITS:
        for it in data.get(split, []):
            if it["category"] == "word_2step" and it["answer"] < 0:
                fail(f"{it['id']}: word_2step answer is negative "
                     f"({it['answer']})")

    # F2c: bare-form share per arithmetic split in 25-35% band
    for split in ARITH_SPLITS:
        items = data.get(split, [])
        if items:
            nb = sum(1 for it in items if is_bare(it["prompt"]))
            share = nb / len(items)
            notes.append(f"{split}: bare-form {nb}/{len(items)} "
                         f"({share:.1%})")
            if not (0.25 <= share <= 0.35):
                fail(f"{split}: bare-form share {share:.1%} outside "
                     f"25-35% band ({nb}/{len(items)})")

    # N1: independent prompt-parsing recompute
    parsed = 0
    arith_total = 0
    for split in ARITH_SPLITS:
        for it in data.get(split, []):
            arith_total += 1
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
    if arith_total:
        cov = parsed / arith_total
        notes.append(f"prompt-parse: {parsed}/{arith_total} arithmetic "
                     f"items parsed ({cov:.1%} coverage)")
        if cov < 0.60:
            fail(f"prompt-parse coverage {cov:.1%} < 60% "
                 f"({parsed}/{arith_total})")

    # N2: prompt uniqueness WITHIN each file too
    for name, items in data.items():
        prompts = [(it.get("prompt") or it.get("text")) for it in items]
        if len(set(prompts)) != len(prompts):
            fail(f"{name}: prompts not unique within file "
                 f"({len(set(prompts))} unique of {len(prompts)})")
        else:
            notes.append(f"{name}: within-file prompt uniqueness OK")

    # prompt uniqueness across ALL files
    owner = {}
    for name, items in data.items():
        for it in items:
            p = it.get("prompt") or it.get("text")
            if p in owner and owner[p] != name:
                fail(f"prompt shared between {owner[p]} and {name}: "
                     f"{p[:60]!r}")
            owner.setdefault(p, name)

    # heldout must carry no set-A marker (N3: list from the
    # generator-emitted setA_markers.json, not a hand list)
    markers = load_markers()
    notes.append(f"setA markers: {len(markers)} markers loaded")
    if not markers:
        fail("setA markers list is empty")
    for it in data.get("heldout", []):
        for marker in markers:
            # Word-boundary appearance: a marker counts only as a
            # whole word / phrase, so pool-B "notebooks" is not a
            # hit for pool-A "books" (same token-boundary rule as
            # fact matching, F1).
            if marker and re.search(
                    r"(?<![A-Za-z0-9])" + re.escape(marker)
                    + r"(?![A-Za-z0-9])", it["prompt"]):
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
                      ("solar_system", 15), ("conversions", 14),
                      ("misc", 16)]:
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
          "uniqueness (within-file and cross-file), prompt-parse "
          "recompute, bare-form share, word_2step non-negativity, "
          "heldout marker hygiene, and structural checks all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
