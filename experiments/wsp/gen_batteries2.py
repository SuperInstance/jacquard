#!/usr/bin/env python3
"""Seeded generator for Jacquard Phase 15, slice 42 (E5 batteries).

Extends gen_batteries.py with two NEW task families for the
successive-task forgetting study. The patcher never builds these.

Writes (paths relative to this script):
  batteries/t2_diagnostic.jsonl   60 date/interval items (set A2)
  private/t2_heldout.jsonl       120 date/interval items (set B2)
  batteries/t3_diagnostic.jsonl   60 unit-conversion items (set A2)
  private/t3_heldout.jsonl       120 unit-conversion items (set B2)
  batteries/setA2_markers.json    pool-A2 strings + set-A2 fragments

Python stdlib only. Fully deterministic: fixed seeds, no wall
clock, no environment dependence. All t2 golds are computed with
datetime; all t3 golds are exact (integers or exact 2-decimals).

Uniqueness discipline matches gen_batteries.py and extends it:
prompt strings AND derivation strings are globally unique across
ALL arithmetic splits, old and new. The seen-sets are seeded from
the slice-41 files on disk before any new item is generated.
Run:  python3 gen_batteries2.py
"""
import calendar
import datetime
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

SEED_T2_DIAG = 15046
SEED_T2_HELD = 15047
SEED_T3_DIAG = 15048
SEED_T3_HELD = 15049

END = "Answer with just the number."
YEAR = 2025  # a non-leap year: no leap-day ambiguity anywhere

T2_CATEGORIES = ["days_between", "weekday_offset", "add_days_count",
                 "weeks_days", "month_span"]
T3_CATEGORIES = ["time_conv", "metric_length", "imperial_length",
                 "dozen_gross", "metric_mass", "metric_volume"]

# ---------------- lexical pools (disjoint from slice-41 pools) ----
NAMES_A2 = ["Harper", "Oscar", "Clara", "Hugo", "Rosa", "Ben",
            "Ivy", "Samuel"]
OBJECTS_A2 = ["screws", "candles", "postcards", "muffins",
              "napkins", "pebbles", "planks", "bottles"]
NAMES_B2 = ["Yuki", "Omar", "Lena", "Ravi", "Astrid", "Diego",
            "Mei", "Karl"]

MONTH_NAMES = ["January", "February", "March", "April", "May",
               "June", "July", "August", "September", "October",
               "November", "December"]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
WEEKDAY_MAP = ("Monday=1, Tuesday=2, Wednesday=3, Thursday=4, "
               "Friday=5, Saturday=6, Sunday=7")
MONTH_MAP = ("January=1, February=2, March=3, April=4, May=5, "
             "June=6, July=7, August=8, September=9, October=10, "
             "November=11, December=12")

# ---- set-A2 markers ----
# Template frame fragments that occur in set-A2 templates (exact
# substrings of the a2_* prompts). Emitted, together with all
# pool-A2 strings, to batteries/setA2_markers.json; the verifier
# asserts none of them (and none of the slice-41 set-A markers)
# appears in any new heldout prompt.
SET_A2_FRAGMENTS = [
    "Convert", "how many days pass from", "What weekday is it",
    "falls in which month", "are left in the month after",
    "whole weeks are there", "how many whole months are there from",
    "How many leftover days", "split into whole weeks",
    "Give the month number", "on the trip that runs from",
    "journey lasts", "ribbon measures", "sack weighs",
    "tank holds",
]

# ---- deterministic variant alternation (mirrors _is_bare) ----
_variant_counts = {}


def _alt(key):
    i = _variant_counts.get(key, 0)
    _variant_counts[key] = i + 1
    return i % 2 == 0


# ================= shared date helpers =================

def _date_from_ordinal(rng, lo, hi):
    base = datetime.date(YEAR, 1, 1)
    return base + datetime.timedelta(days=rng.randint(lo, hi))


def _fmt_a(d):
    return f"{d.day} {MONTH_NAMES[d.month - 1]} {YEAR}"


def _fmt_b(d):
    return f"{MONTH_NAMES[d.month - 1]} {d.day}, {YEAR}"


def _doy(d):
    return d.timetuple().tm_yday


def _whole_months(d1, d2):
    """Complete calendar months from d1 to d2 (same year): the
    month difference, minus one if d2's day-of-month has not yet
    reached d1's day-of-month."""
    n = d2.month - d1.month
    if d2.day < d1.day:
        n -= 1
    return n


# ================= T2 SET A2 (diagnostic) =================

def a2_days_between(rng):
    start = rng.randint(0, 300)
    gap = rng.randint(5, 60)
    base = datetime.date(YEAR, 1, 1)
    d1 = base + datetime.timedelta(days=start)
    d2 = base + datetime.timedelta(days=start + gap)
    ans = (d2 - d1).days
    deriv = f"{_doy(d2)} - {_doy(d1)}"
    if _alt("a2_db"):
        p = (f"In {YEAR}, how many days pass from {_fmt_a(d1)} to "
             f"{_fmt_a(d2)}? {END}")
    else:
        name = rng.choice(NAMES_A2)
        p = (f"{name} is on the trip that runs from {_fmt_a(d1)} to "
             f"{_fmt_a(d2)} in {YEAR}. How many days pass from the "
             f"first date to the second? {END}")
    return p, ans, deriv


def a2_weekday_offset(rng):
    d = _date_from_ordinal(rng, 0, 364)
    w = d.isoweekday()
    wd = WEEKDAY_NAMES[w - 1]
    n = rng.randint(2, 40)
    ans = (d + datetime.timedelta(days=n)).isoweekday()
    k = (w - 1 + n) // 7
    if k == 0:
        deriv = f"{w} + {n}"
    else:
        deriv = f"{w} + {n} - {7 * k}"
    p = (f"{_fmt_a(d)} is a {wd}. What weekday is it {n} days "
         f"later? Use the mapping {WEEKDAY_MAP}. {END}")
    return p, ans, deriv


def a2_add_days_count(rng):
    if _alt("a2_adc"):
        # variant 1: start date + N days lands in which month
        d = _date_from_ordinal(rng, 0, 270)
        n = rng.randint(5, 90)
        t = d + datetime.timedelta(days=n)
        ans = t.month
        deriv = f"max({d.month}, {t.month})"
        p = (f"Start at {_fmt_a(d)} and move forward {n} days. "
             f"The date you reach falls in which month? Give the "
             f"month number, where {MONTH_MAP}. {END}")
        return p, ans, deriv
    # variant 2: days from a date to the end of its month
    d = _date_from_ordinal(rng, 0, 364)
    dim = calendar.monthrange(YEAR, d.month)[1]
    while d.day > dim - 2:
        d = _date_from_ordinal(rng, 0, 364)
        dim = calendar.monthrange(YEAR, d.month)[1]
    ans = dim - d.day
    deriv = f"{dim} - {d.day}"
    p = (f"How many days are left in the month after {_fmt_a(d)}, "
         f"not counting that day itself? {END}")
    return p, ans, deriv


def a2_weeks_days(rng):
    n = rng.randint(11, 120)
    if _alt("a2_wd"):
        ans = n // 7
        deriv = f"({n} - {n % 7}) / 7"
        p = (f"{n} days can be split into whole weeks plus "
             f"leftover days. How many whole weeks are there? {END}")
        return p, ans, deriv
    while n % 7 == 0:
        n += 1
    ans = n % 7
    deriv = f"{n} - {n // 7} * 7"
    p = (f"{n} days can be split into whole weeks plus leftover "
         f"days. How many leftover days are there? {END}")
    return p, ans, deriv


def a2_month_span(rng):
    m1 = rng.randint(1, 10)
    m2 = rng.randint(m1 + 1, 12)
    day1 = rng.randint(1, 28)
    day2 = rng.randint(1, 28)
    d1 = datetime.date(YEAR, m1, day1)
    d2 = datetime.date(YEAR, m2, day2)
    ans = _whole_months(d1, d2)
    if ans < 1:
        day2 = day1
        d2 = datetime.date(YEAR, m2, day2)
        ans = _whole_months(d1, d2)
    if day2 >= day1:
        deriv = f"{m2} - {m1}"
    else:
        deriv = f"{m2} - {m1} - 1"
    p = (f"In {YEAR}, how many whole months are there from "
         f"{_fmt_a(d1)} to {_fmt_a(d2)}? A whole month means the "
         f"same day-of-month has been reached again. {END}")
    return p, ans, deriv


GEN_T2_A = {"days_between": a2_days_between,
            "weekday_offset": a2_weekday_offset,
            "add_days_count": a2_add_days_count,
            "weeks_days": a2_weeks_days,
            "month_span": a2_month_span}

# ================= T2 SET B2 (heldout only) =================
# Separate code, different surface forms from set A2. None of the
# set-A or set-A2 marker phrases may appear in any set-B2 prompt.

def b2_days_between(rng):
    start = rng.randint(0, 300)
    gap = rng.randint(5, 60)
    base = datetime.date(YEAR, 1, 1)
    d1 = base + datetime.timedelta(days=start)
    d2 = base + datetime.timedelta(days=start + gap)
    ans = (d2 - d1).days
    deriv = f"{_doy(d2)} - {_doy(d1)}"
    p = (f"Count the days between {_fmt_b(d1)} and {_fmt_b(d2)} "
         f"in the year {YEAR}. The count is what? {END}")
    return p, ans, deriv


def b2_weekday_offset(rng):
    d = _date_from_ordinal(rng, 0, 364)
    w = d.isoweekday()
    wd = WEEKDAY_NAMES[w - 1]
    n = rng.randint(2, 40)
    ans = (d + datetime.timedelta(days=n)).isoweekday()
    k = (w - 1 + n) // 7
    if k == 0:
        deriv = f"{w} + {n}"
    else:
        deriv = f"{w} + {n} - {7 * k}"
    p = (f"In the year {YEAR}, {_fmt_b(d)} falls on a {wd}. "
         f"{n} days afterwards, the weekday number is what? "
         f"Weekday numbers run {WEEKDAY_MAP}. {END}")
    return p, ans, deriv


def b2_add_days_count(rng):
    if _alt("b2_adc"):
        d = _date_from_ordinal(rng, 0, 270)
        n = rng.randint(5, 90)
        t = d + datetime.timedelta(days=n)
        ans = t.month
        deriv = f"max({d.month}, {t.month})"
        p = (f"Beginning at {_fmt_b(d)}, advance {n} days through "
             f"the calendar. You arrive at a date whose month "
             f"number is what? Month numbers run {MONTH_MAP}. {END}")
        return p, ans, deriv
    d = _date_from_ordinal(rng, 0, 364)
    dim = calendar.monthrange(YEAR, d.month)[1]
    while d.day > dim - 2:
        d = _date_from_ordinal(rng, 0, 364)
        dim = calendar.monthrange(YEAR, d.month)[1]
    ans = dim - d.day
    deriv = f"{dim} - {d.day}"
    p = (f"From {_fmt_b(d)}, how many days remain until the month "
         f"ends, excluding the starting day? {END}")
    return p, ans, deriv


def b2_weeks_days(rng):
    n = rng.randint(11, 120)
    if _alt("b2_wd"):
        ans = n // 7
        deriv = f"({n} - {n % 7}) / 7"
        p = (f"A span of {n} days contains some complete weeks "
             f"and a remainder. Give the number of complete weeks. "
             f"{END}")
        return p, ans, deriv
    while n % 7 == 0:
        n += 1
    ans = n % 7
    deriv = f"{n} - {n // 7} * 7"
    p = (f"A span of {n} days contains some complete weeks and a "
         f"remainder. Give the remainder, in days. {END}")
    return p, ans, deriv


def b2_month_span(rng):
    m1 = rng.randint(1, 10)
    m2 = rng.randint(m1 + 1, 12)
    day1 = rng.randint(1, 28)
    day2 = rng.randint(1, 28)
    d1 = datetime.date(YEAR, m1, day1)
    d2 = datetime.date(YEAR, m2, day2)
    ans = _whole_months(d1, d2)
    if ans < 1:
        day2 = day1
        d2 = datetime.date(YEAR, m2, day2)
        ans = _whole_months(d1, d2)
    if day2 >= day1:
        deriv = f"{m2} - {m1}"
    else:
        deriv = f"{m2} - {m1} - 1"
    p = (f"Between {_fmt_b(d1)} and {_fmt_b(d2)} in the year "
         f"{YEAR}, how many complete months elapse, where a "
         f"complete month ends when the starting day-of-month "
         f"comes round again? The count is what? {END}")
    return p, ans, deriv


GEN_T2_B = {"days_between": b2_days_between,
            "weekday_offset": b2_weekday_offset,
            "add_days_count": b2_add_days_count,
            "weeks_days": b2_weeks_days,
            "month_span": b2_month_span}

# ================= T3 conversion tables =================
# unit -> factor to the category base unit (exact integers).
TIME_UNITS = {"seconds": 1, "minutes": 60, "hours": 3600,
              "days": 86400}
MLEN_UNITS = {"millimetres": 1, "centimetres": 10, "metres": 1000,
              "kilometres": 1000000}
ILEN_UNITS = {"inches": 1, "feet": 12, "yards": 36, "miles": 63360}
DOZEN_UNITS = {"items": 1, "dozen": 12, "gross": 144}
MASS_UNITS = {"grams": 1, "kilograms": 1000, "tonnes": 1000000}
VOL_UNITS = {"millilitres": 1, "litres": 1000,
             "cubic metres": 1000000}

# (from, to) pairs; both directions represented per category.
TIME_PAIRS = [("hours", "minutes"), ("minutes", "hours"),
              ("minutes", "seconds"), ("seconds", "minutes"),
              ("days", "hours"), ("hours", "days")]
MLEN_PAIRS = [("kilometres", "metres"), ("metres", "kilometres"),
              ("metres", "centimetres"), ("centimetres", "metres"),
              ("centimetres", "millimetres"),
              ("millimetres", "centimetres"),
              ("metres", "millimetres"), ("millimetres", "metres")]
ILEN_PAIRS = [("miles", "feet"), ("feet", "miles"),
              ("yards", "feet"), ("feet", "yards"),
              ("feet", "inches"), ("inches", "feet")]
DOZEN_PAIRS = [("dozen", "items"), ("items", "dozen"),
               ("gross", "items"), ("items", "gross"),
               ("dozen", "gross"), ("gross", "dozen")]
MASS_PAIRS = [("tonnes", "kilograms"), ("kilograms", "tonnes"),
              ("kilograms", "grams"), ("grams", "kilograms"),
              ("tonnes", "grams")]
VOL_PAIRS = [("litres", "millilitres"), ("millilitres", "litres"),
             ("cubic metres", "litres"), ("litres", "cubic metres"),
             ("cubic metres", "millilitres")]

T3_SPEC = {
    "time_conv": (TIME_UNITS, TIME_PAIRS),
    "metric_length": (MLEN_UNITS, MLEN_PAIRS),
    "imperial_length": (ILEN_UNITS, ILEN_PAIRS),
    "dozen_gross": (DOZEN_UNITS, DOZEN_PAIRS),
    "metric_mass": (MASS_UNITS, MASS_PAIRS),
    "metric_volume": (VOL_UNITS, VOL_PAIRS),
}

# Context openers for set-A2 frame 2, per category. The {v} and
# {uf} slots carry the value and source unit.
A2_CONTEXT = {
    "time_conv": [
        "A train journey lasts {v} {uf}.",
        "A film runs for {v} {uf}.",
    ],
    "metric_length": [
        "A ribbon measures {v} {uf} in length.",
        "A garden path stretches {v} {uf}.",
    ],
    "imperial_length": [
        "A hiking trail stretches {v} {uf}.",
        "A rope is {v} {uf} long.",
    ],
    "dozen_gross": [
        "A supplier ships {v} {uf} of screws.",
        "A bakery orders {v} {uf} of muffins.",
    ],
    "metric_mass": [
        "A sack weighs {v} {uf}.",
        "A crate has a mass of {v} {uf}.",
    ],
    "metric_volume": [
        "A tank holds {v} {uf} of water.",
        "A jug contains {v} {uf} of juice.",
    ],
}


def _conversion(rng, cat):
    """Draw one exact conversion: (value, from, to, answer, deriv).

    Downhill (to a smaller unit): integer value, integer result,
    derivation "v * ratio". Uphill: the result is drawn first so
    the value is exact; for divisors 100/1000 a quarter offset is
    sometimes added, giving an exact 2-decimal result and a
    derivation "v / divisor"."""
    units, pairs = T3_SPEC[cat]
    uf, ut = pairs[rng.randrange(len(pairs))]
    fu, ft = units[uf], units[ut]
    if fu > ft:
        ratio = fu // ft
        v = rng.randint(2, 40)
        if uf == "miles":
            v = rng.randint(2, 20)
        ans = v * ratio
        return v, uf, ut, ans, f"{v} * {ratio}"
    divisor = ft // fu
    if divisor in (100, 1000) and rng.randrange(3) == 0:
        r = rng.randint(1, 12)
        extra = rng.choice([divisor // 4, divisor // 2,
                            3 * divisor // 4])
        v = r * divisor + extra
        ans = round(v / divisor, 2)
        return v, uf, ut, ans, f"{v} / {divisor}"
    r = rng.randint(2, 40)
    if ut == "miles":
        r = rng.randint(2, 12)
    v = r * divisor
    return v, uf, ut, r, f"{v} / {divisor}"


def _make_t3_a(cat):
    def gen(rng):
        v, uf, ut, ans, deriv = _conversion(rng, cat)
        if _alt("a3_" + cat):
            p = f"Convert {v} {uf} to {ut}. {END}"
        else:
            ctx = rng.choice(A2_CONTEXT[cat])
            # dozen_gross contexts name a counted object only when
            # the source unit is dozen/gross; for items the generic
            # frame below is used instead.
            if cat == "dozen_gross" and uf == "items":
                p = (f"A stall packs {v} {uf} into boxes. How many "
                     f"{ut} is that? {END}")
            else:
                p = (ctx.format(v=v, uf=uf)
                     + f" How many {ut} is that? {END}")
        return p, ans, deriv
    return gen


def _make_t3_b(cat):
    def gen(rng):
        v, uf, ut, ans, deriv = _conversion(rng, cat)
        k = rng.randrange(3)
        if k == 0:
            p = f"How many {ut} are in {v} {uf}? {END}"
        elif k == 1:
            p = f"{v} {uf} equals how many {ut}? {END}"
        else:
            name = rng.choice(NAMES_B2)
            p = (f"{name} checks a quantity of {v} {uf}. Stated "
                 f"in {ut}, the amount is what? {END}")
        return p, ans, deriv
    return gen


GEN_T3_A = {cat: _make_t3_a(cat) for cat in T3_CATEGORIES}
GEN_T3_B = {cat: _make_t3_b(cat) for cat in T3_CATEGORIES}

# ================= split builder =================

OLD_FILES = [HERE / "batteries" / "diagnostic.jsonl",
             HERE / "batteries" / "validation.jsonl",
             HERE / "private" / "heldout.jsonl",
             HERE / "private" / "forget_instr.jsonl",
             HERE / "private" / "forget_fact.jsonl",
             HERE / "private" / "forget_prose.jsonl"]


def seed_seen():
    """Seed the seen-sets from every slice-41 file so no prompt or
    derivation from the first instrument can recur in the new one."""
    seen_prompts, seen_derivs = set(), set()
    for path in OLD_FILES:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                it = json.loads(line)
                p = it.get("prompt") or it.get("text")
                if p:
                    seen_prompts.add(p)
                if it.get("derivation"):
                    seen_derivs.add(it["derivation"])
    return seen_prompts, seen_derivs


def build_split(split, prefix, seed, per_cat, gens, categories,
                seen_prompts, seen_derivs):
    rng = random.Random(seed)
    items = []
    n = 0
    for cat in categories:
        made = 0
        attempts = 0
        while made < per_cat:
            attempts += 1
            if attempts > 20000:
                raise RuntimeError(f"cannot fill {split}/{cat}")
            prompt, answer, deriv = gens[cat](rng)
            if prompt in seen_prompts or deriv in seen_derivs:
                continue
            seen_prompts.add(prompt)
            seen_derivs.add(deriv)
            n += 1
            items.append({"id": f"{prefix}-{n:03d}", "split": split,
                          "category": cat, "prompt": prompt,
                          "answer": answer, "derivation": deriv})
            made += 1
    return items


def write_jsonl(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def main():
    seen_prompts, seen_derivs = seed_seen()
    t2d = build_split("t2_diagnostic", "t2diag", SEED_T2_DIAG, 12,
                      GEN_T2_A, T2_CATEGORIES, seen_prompts,
                      seen_derivs)
    t2h = build_split("t2_heldout", "t2held", SEED_T2_HELD, 24,
                      GEN_T2_B, T2_CATEGORIES, seen_prompts,
                      seen_derivs)
    t3d = build_split("t3_diagnostic", "t3diag", SEED_T3_DIAG, 10,
                      GEN_T3_A, T3_CATEGORIES, seen_prompts,
                      seen_derivs)
    t3h = build_split("t3_heldout", "t3held", SEED_T3_HELD, 20,
                      GEN_T3_B, T3_CATEGORIES, seen_prompts,
                      seen_derivs)
    assert len(t2d) == 60 and len(t2h) == 120
    assert len(t3d) == 60 and len(t3h) == 120
    markers = {
        "pool_a2": {"names": NAMES_A2, "objects": OBJECTS_A2},
        "template_frames_a2": SET_A2_FRAGMENTS,
        "markers": NAMES_A2 + OBJECTS_A2 + SET_A2_FRAGMENTS,
    }
    (HERE / "batteries" / "setA2_markers.json").write_text(
        json.dumps(markers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    write_jsonl(HERE / "batteries" / "t2_diagnostic.jsonl", t2d)
    write_jsonl(HERE / "private" / "t2_heldout.jsonl", t2h)
    write_jsonl(HERE / "batteries" / "t3_diagnostic.jsonl", t3d)
    write_jsonl(HERE / "private" / "t3_heldout.jsonl", t3h)
    for name, items in [("t2_diagnostic", t2d), ("t2_heldout", t2h),
                        ("t3_diagnostic", t3d), ("t3_heldout", t3h)]:
        print(f"{name}: {len(items)} items")


if __name__ == "__main__":
    main()
