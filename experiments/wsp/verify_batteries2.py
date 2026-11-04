#!/usr/bin/env python3
"""Independent verification of the slice-42 (E5) batteries.

Re-checks, WITHOUT importing gen_batteries2.py, and using the
slice-41 files as cross-reference:
  * exact item counts and per-category balance for the four new
    splits (t2_diagnostic 60, t2_heldout 120, t3_diagnostic 60,
    t3_heldout 120)
  * every new derivation: parsed with the same restricted AST
    evaluator as verify_batteries.py (+ - * /, parentheses,
    numeric literals, max()/min()), recomputed, compared to the
    stored answer (exact for integers, |diff| <= 0.005 otherwise)
  * every new answer is a JSON number, integral or exact
    2-decimal; every new prompt ends with
    "Answer with just the number."
  * prompt uniqueness within each new file and across ALL battery
    files (the six slice-41 files plus the four new ones)
  * derivation uniqueness across ALL arithmetic files (the three
    slice-41 arithmetic splits plus the four new ones)
  * heldout marker hygiene for t2_heldout and t3_heldout against
    BOTH batteries/setA_markers.json (slice 41) and
    batteries/setA2_markers.json (slice 42), word-boundary based
  * every weekday_offset prompt states the weekday mapping, and
    the weekday it states for its date is the true 2025 weekday
  * an independent prompt-parsing recompute for the new families:
    fresh regex/datetime logic here extracts dates, spans and
    unit conversions from the prompt TEXT (never the derivation)
    and the parsed answer must equal the stored answer; the run
    FAILS if parse coverage is below 60% for either new family

Prints a PASS/FAIL summary. Exit code 0 iff all checks pass.
Run:  python3 verify_batteries2.py
"""
import ast
import calendar
import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

NEW_FILES = {
    "t2_diagnostic": (HERE / "batteries" / "t2_diagnostic.jsonl", 60),
    "t2_heldout": (HERE / "private" / "t2_heldout.jsonl", 120),
    "t3_diagnostic": (HERE / "batteries" / "t3_diagnostic.jsonl", 60),
    "t3_heldout": (HERE / "private" / "t3_heldout.jsonl", 120),
}
OLD_FILES = {
    "diagnostic": HERE / "batteries" / "diagnostic.jsonl",
    "validation": HERE / "batteries" / "validation.jsonl",
    "heldout": HERE / "private" / "heldout.jsonl",
    "forget_instr": HERE / "private" / "forget_instr.jsonl",
    "forget_fact": HERE / "private" / "forget_fact.jsonl",
    "forget_prose": HERE / "private" / "forget_prose.jsonl",
}
OLD_ARITH = ["diagnostic", "validation", "heldout"]
T2_CATEGORIES = ["days_between", "weekday_offset", "add_days_count",
                 "weeks_days", "month_span"]
T3_CATEGORIES = ["time_conv", "metric_length", "imperial_length",
                 "dozen_gross", "metric_mass", "metric_volume"]
PER_CAT = {"t2_diagnostic": 12, "t2_heldout": 24,
           "t3_diagnostic": 10, "t3_heldout": 20}
END = "Answer with just the number."
YEAR = 2025

failures = []
notes = []


def fail(msg):
    failures.append(msg)


# ---- restricted AST evaluator (same rules as verify_batteries) ----

def eval_derivation(expr):
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


def load_markers(path, label):
    if not path.exists():
        fail(f"{label} markers file missing: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fail(f"{label} markers file unparseable: {e}")
        return []
    if isinstance(data, dict) and isinstance(data.get("markers"), list):
        return [str(m) for m in data["markers"]]
    if isinstance(data, list):
        return [str(m) for m in data]
    fail(f"{label} markers file has no 'markers' list")
    return []


# ---- independent prompt-parsing recompute (new families) ----
# Fresh logic written for this verifier. It reads ONLY the prompt
# text (plus the item category) -- never the derivation string.

MONTH_IDX = {name: i + 1 for i, name in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November",
     "December"])}
_MONTH_ALT = "|".join(MONTH_IDX)
_DATE_A = re.compile(r"(\d{1,2}) (" + _MONTH_ALT + r") 2025")
_DATE_B = re.compile(r"(" + _MONTH_ALT + r") (\d{1,2}), 2025")
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]


def find_dates(prompt):
    """All 2025 dates stated in the prompt, in order of appearance
    (both '10 March 2025' and 'March 10, 2025' surface forms)."""
    found = []
    for m in _DATE_A.finditer(prompt):
        found.append((m.start(), datetime.date(
            YEAR, MONTH_IDX[m.group(2)], int(m.group(1)))))
    for m in _DATE_B.finditer(prompt):
        found.append((m.start(), datetime.date(
            YEAR, MONTH_IDX[m.group(1)], int(m.group(2)))))
    return [d for _, d in sorted(found)]


def _whole_months(d1, d2):
    n = d2.month - d1.month
    if d2.day < d1.day:
        n -= 1
    return n


def parse_t2(item):
    prompt, cat = item["prompt"], item["category"]
    dates = find_dates(prompt)
    if cat == "days_between":
        if len(dates) >= 2:
            return (dates[1] - dates[0]).days
        return None
    if cat == "weekday_offset":
        m = re.search(r"(\d+) days (?:later|afterwards)", prompt)
        if dates and m:
            return (dates[0] + datetime.timedelta(
                days=int(m.group(1)))).isoweekday()
        return None
    if cat == "add_days_count":
        if "month number" in prompt or "which month" in prompt:
            m = re.search(r"(?:move forward|advance) (\d+) days",
                          prompt)
            if dates and m:
                return (dates[0] + datetime.timedelta(
                    days=int(m.group(1)))).month
            return None
        if dates:
            dim = calendar.monthrange(YEAR, dates[0].month)[1]
            return dim - dates[0].day
        return None
    if cat == "weeks_days":
        m = re.search(r"(\d+) days can be split", prompt) or \
            re.search(r"span of (\d+) days", prompt)
        if not m:
            return None
        n = int(m.group(1))
        if "How many whole weeks are there" in prompt or \
                "Give the number of complete weeks" in prompt:
            return n // 7
        if "How many leftover days" in prompt or \
                "Give the remainder, in days" in prompt:
            return n % 7
        return None
    if cat == "month_span":
        if len(dates) >= 2:
            return _whole_months(dates[0], dates[1])
        return None
    return None


# unit -> factor to its family base unit (exact)
UNIT_FACTORS = {
    "seconds": 1, "minutes": 60, "hours": 3600, "days": 86400,
    "millimetres": 1, "centimetres": 10, "metres": 1000,
    "kilometres": 1000000,
    "inches": 1, "feet": 12, "yards": 36, "miles": 63360,
    "items": 1, "dozen": 12, "gross": 144,
    "grams": 1, "kilograms": 1000, "tonnes": 1000000,
    "millilitres": 1, "litres": 1000, "cubic metres": 1000000,
}
_UNIT_ALT = "|".join(sorted(UNIT_FACTORS, key=len, reverse=True))
_UNIT_RE = re.compile(r"(" + _UNIT_ALT + r")\b")
_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?) (" + _UNIT_ALT + r")\b")


def parse_t3(item):
    prompt = item["prompt"]
    m = _VALUE_RE.search(prompt)
    if not m:
        return None
    value = float(m.group(1))
    from_unit = m.group(2)
    target = None
    for um in _UNIT_RE.finditer(prompt):
        if um.start() == m.start(2):
            continue  # the source unit itself
        target = um.group(1)
        break
    if target is None:
        return None
    return value * UNIT_FACTORS[from_unit] / UNIT_FACTORS[target]


def main():
    data = {}
    for name, (path, expected) in NEW_FILES.items():
        if not path.exists():
            fail(f"{name}: file missing: {path}")
            continue
        data[name] = load(path)
        if len(data[name]) != expected:
            fail(f"{name}: count {len(data[name])} != expected "
                 f"{expected}")
        else:
            notes.append(f"{name}: count {len(data[name])} OK")

    old_data = {}
    for name, path in OLD_FILES.items():
        if not path.exists():
            fail(f"slice-41 file missing (needed for cross-checks): "
                 f"{path}")
            continue
        old_data[name] = load(path)

    # counts per category, split field, suffix, answer shape,
    # derivation recompute
    for split, items in data.items():
        cats = T2_CATEGORIES if split.startswith("t2") \
            else T3_CATEGORIES
        counts = Counter(it["category"] for it in items)
        for cat in cats:
            if counts.get(cat, 0) != PER_CAT[split]:
                fail(f"{split}/{cat}: {counts.get(cat, 0)} != "
                     f"{PER_CAT[split]}")
        for it in items:
            if it.get("split") != split:
                fail(f"{it['id']}: split field is "
                     f"{it.get('split')!r}")
            if not it["prompt"].endswith(END):
                fail(f"{it['id']}: prompt does not end with the "
                     f"required sentence")
            gold = it["answer"]
            if not isinstance(gold, (int, float)) \
                    or isinstance(gold, bool):
                fail(f"{it['id']}: answer is not a JSON number: "
                     f"{gold!r}")
                continue
            if abs(gold - round(gold, 2)) > 1e-9:
                fail(f"{it['id']}: answer {gold} is not integral "
                     f"or exact 2-decimal")
            try:
                value = eval_derivation(it["derivation"])
            except Exception as e:  # noqa: BLE001
                fail(f"{it['id']}: derivation unparseable: {e}")
                continue
            if isinstance(gold, int):
                if value != gold:
                    fail(f"{it['id']}: derivation gives {value}, "
                         f"stored answer {gold}")
            elif abs(value - gold) > 0.005:
                fail(f"{it['id']}: derivation gives {value}, "
                     f"stored answer {gold}")

    # weekday_offset: mapping stated, stated weekday is truthful
    for split in ("t2_diagnostic", "t2_heldout"):
        for it in data.get(split, []):
            if it["category"] != "weekday_offset":
                continue
            p = it["prompt"]
            if "Monday=1" not in p or "Sunday=7" not in p:
                fail(f"{it['id']}: weekday mapping not stated in "
                     f"prompt")
            dates = find_dates(p)
            m = re.search(r"(?:is a|falls on a) (\w+day)", p)
            if dates and m:
                true_name = WEEKDAY_NAMES[dates[0].isoweekday() - 1]
                if m.group(1) != true_name:
                    fail(f"{it['id']}: prompt states weekday "
                         f"{m.group(1)} but the date is a "
                         f"{true_name}")
            else:
                fail(f"{it['id']}: weekday statement not parseable")

    # prompt uniqueness WITHIN each new file
    for name, items in data.items():
        prompts = [it["prompt"] for it in items]
        if len(set(prompts)) != len(prompts):
            fail(f"{name}: prompts not unique within file "
                 f"({len(set(prompts))} unique of {len(prompts)})")
        else:
            notes.append(f"{name}: within-file prompt uniqueness OK")

    # prompt uniqueness across ALL files (slice 41 + slice 42)
    owner = {}
    for name, items in list(old_data.items()) + list(data.items()):
        for it in items:
            p = it.get("prompt") or it.get("text")
            if p is None:
                continue
            if p in owner and owner[p] != name:
                fail(f"prompt shared between {owner[p]} and "
                     f"{name}: {p[:60]!r}")
            owner.setdefault(p, name)
    notes.append("cross-file prompt uniqueness checked against "
                 "all slice-41 files")

    # derivation uniqueness across ALL arithmetic files
    downer = {}
    arith_all = {k: old_data[k] for k in OLD_ARITH if k in old_data}
    arith_all.update(data)
    for name, items in arith_all.items():
        for it in items:
            d = it.get("derivation")
            if d is None:
                continue
            if d in downer and downer[d] != (name, it["id"]):
                fail(f"derivation {d!r} shared between "
                     f"{downer[d]} and ({name}, {it['id']})")
            downer.setdefault(d, (name, it["id"]))
    notes.append("cross-split derivation uniqueness checked "
                 "against all slice-41 arithmetic files")

    # heldout marker hygiene: BOTH marker files, word-boundary
    markers_a = load_markers(HERE / "batteries" / "setA_markers.json",
                             "setA")
    markers_a2 = load_markers(
        HERE / "batteries" / "setA2_markers.json", "setA2")
    notes.append(f"setA markers: {len(markers_a)} loaded; "
                 f"setA2 markers: {len(markers_a2)} loaded")
    if not markers_a or not markers_a2:
        fail("a marker list is empty")
    for split in ("t2_heldout", "t3_heldout"):
        for it in data.get(split, []):
            for marker in markers_a + markers_a2:
                if marker and re.search(
                        r"(?<![A-Za-z0-9])" + re.escape(marker)
                        + r"(?![A-Za-z0-9])", it["prompt"]):
                    fail(f"{it['id']}: heldout prompt contains "
                         f"set-A/A2 marker {marker!r}")

    # independent prompt-parsing recompute, per family
    for family, parser in (("t2", parse_t2), ("t3", parse_t3)):
        parsed = 0
        total = 0
        for split, items in data.items():
            if not split.startswith(family):
                continue
            for it in items:
                total += 1
                try:
                    pv = parser(it)
                except Exception as e:  # noqa: BLE001
                    fail(f"{it['id']}: prompt parser raised: {e}")
                    continue
                if pv is None:
                    continue
                parsed += 1
                if abs(float(pv) - float(it["answer"])) > 0.005:
                    fail(f"{it['id']}: prompt-parsed answer {pv} "
                         f"!= stored answer {it['answer']}")
        if total:
            cov = parsed / total
            notes.append(f"prompt-parse {family}: {parsed}/{total} "
                         f"items parsed ({cov:.1%} coverage)")
            if cov < 0.60:
                fail(f"prompt-parse {family} coverage {cov:.1%} "
                     f"< 60% ({parsed}/{total})")

    print("=== battery verification (slice 42) ===")
    for n in notes:
        print("  " + n)
    if failures:
        print(f"FAIL ({len(failures)} problems)")
        for msg in failures[:50]:
            print("  FAIL: " + msg)
        return 1
    print("PASS: counts, category balance, derivations, answer "
          "shape, prompt uniqueness (within-file and cross-file "
          "vs slice 41), cross-split derivation dedup (vs slice "
          "41), heldout marker hygiene (setA + setA2), weekday "
          "mapping/truthfulness, and prompt-parse recompute all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
