#!/usr/bin/env python3
"""Seeded battery generator for Jacquard Phase 15 (weight-space programming).

Writes (paths relative to this script):
  batteries/diagnostic.jsonl   80 arithmetic items  (template set A, pool A)
  batteries/validation.jsonl   200 arithmetic items (template set A, pool A)
  private/heldout.jsonl        200 arithmetic items (template set B, pool B)
  private/forget_instr.jsonl   100 instruction-format items
  private/forget_fact.jsonl    100 short factual QA items (fixed tables)
  private/forget_prose.jsonl   24 prose paragraphs {"id","text"}

Python stdlib only. Fully deterministic: fixed seeds, no wall clock,
no environment dependence. Run:  python3 gen_batteries.py
"""
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

SEED_DIAGNOSTIC = 15041
SEED_VALIDATION = 15042
SEED_HELDOUT = 15043
SEED_INSTR = 15044
SEED_FACT = 15045

END = "Answer with just the number."
CATEGORIES = ["addsub_chain", "mul_2x1", "mul_2x2", "div_exact",
              "pct_of", "word_2step", "unit_price", "compare"]

# ---------------- lexical pools ----------------
NAMES_A = ["Maya", "Liam", "Sofia", "Noah", "Ava", "Ethan", "Mia", "Lucas"]
OBJECTS_A = ["marbles", "stickers", "pencils", "apples", "books",
             "trading cards", "shells", "buttons"]
SHOPS_A = ["corner shop", "market stall", "school store"]

NAMES_B = ["Priya", "Kenji", "Olga", "Mateo", "Ingrid", "Tariq",
           "Nadia", "Felix"]
OBJECTS_B = ["bolts", "ribbons", "stamps", "peaches", "notebooks",
             "tokens", "beads", "coins"]
SHOPS_B = ["harbour kiosk", "night market", "village bakery"]

# F3: widened percent set.
PCTS = [2, 4, 5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 80, 90]


def pct_base(rng, pct, max_base=400):
    """A base (<= max_base) such that pct% of base is an integer.

    The minimal step is 100/gcd(100, pct): base must be a multiple
    of that step for base * pct / 100 to be integral.
    """
    step = 100 // math.gcd(100, pct)
    return step * rng.randint(1, max_base // step)


# ---- bare-form quota (F2c) ----
# For the five categories that have a bare symbolic form, calls
# alternate bare / non-bare deterministically, so every split lands
# at ~50% bare within those categories and ~31% bare overall
# (125 of 200 items are in bare-capable categories; word_2step,
# unit_price and compare have no bare form in this accounting).
_call_counts = {}


def _is_bare(key):
    i = _call_counts.get(key, 0)
    _call_counts[key] = i + 1
    return i % 2 == 0


# ---- set-A markers (N3) ----
# Template frame fragments that occur in set-A templates (exact
# substrings of the a_* prompts). Emitted, together with all pool-A
# strings, to batteries/setA_markers.json by main(); the verifier
# asserts none of them appears in any heldout prompt.
SET_A_FRAGMENTS = [
    "Compute:", "What is", "Multiply", "Divide", "% of",
    "more and then gave away", "stocked", "in the morning",
    "received a delivery of", "packs of", "in each pack",
    "rows of chairs", "chairs in each row", "shares",
    "equally among", "ride the bus", "of them ride",
    "pages every day", "How many pages are left", "sells",
    "on Monday and", "on Tuesday", "cost of one",
    "does each one cost", "Which is larger",
    "which is the greater one", "Of the numbers",
    "How many students",
]


def unit_price_numbers(rng):
    """(count, total_dollars_float, unit_float) with exact 2-decimal unit."""
    n = rng.randint(2, 12)
    unit_cents = rng.randrange(25, 2001, 25)
    total_cents = unit_cents * n
    return n, total_cents / 100.0, unit_cents / 100.0


# ================= TEMPLATE SET A (diagnostic + validation) =================

def a_addsub_chain(rng):
    name = rng.choice(NAMES_A); obj = rng.choice(OBJECTS_A)
    v = 0 if _is_bare("a_addsub") else rng.randint(1, 2)
    if v == 0:
        a = rng.randint(100, 9999); b = rng.randint(10, 999)
        c = rng.randint(1, a + b - 1)
        p = f"Compute: {a} + {b} - {c}. {END}"
        d = f"{a} + {b} - {c}"
    elif v == 1:
        a = rng.randint(50, 999); b = rng.randint(10, 500)
        c = rng.randint(1, a + b - 1)
        p = (f"{name} had {a} {obj}. {name} bought {b} more and then gave "
             f"away {c}. How many {obj} does {name} have now? {END}")
        d = f"{a} + {b} - {c}"
    else:
        a = rng.randint(100, 900); c = rng.randint(1, a - 1)
        b = rng.randint(10, 500)
        p = (f"A {rng.choice(SHOPS_A)} stocked {a} {obj} in the morning, "
             f"sold {c} during the day, and received a delivery of {b} in "
             f"the evening. How many {obj} are in stock now? {END}")
        d = f"{a} - {c} + {b}"
    return p, eval(d), d


def a_mul_2x1(rng):
    a = rng.randint(12, 99); m = rng.randint(2, 9)
    if _is_bare("a_mul_2x1"):
        p = f"What is {a} * {m}? {END}"
    else:
        name = rng.choice(NAMES_A); obj = rng.choice(OBJECTS_A)
        p = (f"{name} buys {m} packs of {obj} with {a} in each pack. "
             f"How many {obj} does {name} buy in total? {END}")
    d = f"{a} * {m}"
    return p, a * m, d


def a_mul_2x2(rng):
    a = rng.randint(12, 99); b = rng.randint(12, 99)
    v = rng.randrange(2) if _is_bare("a_mul_2x2") else 2
    if v == 0:
        p = f"Multiply {a} by {b}. {END}"
    elif v == 1:
        p = f"What is {a} * {b}? {END}"
    else:
        p = (f"A hall has {a} rows of chairs with {b} chairs in each row. "
             f"How many chairs are there in total? {END}")
    d = f"{a} * {b}"
    return p, a * b, d


def a_div_exact(rng):
    d = rng.randint(2, 12); q = rng.randint(3, 99); n = d * q
    v = rng.randrange(2) if _is_bare("a_div") else 2
    if v == 0:
        p = f"Divide {n} by {d}. {END}"
    elif v == 1:
        p = f"What is {n} / {d}? {END}"
    else:
        name = rng.choice(NAMES_A); obj = rng.choice(OBJECTS_A)
        p = (f"{name} shares {n} {obj} equally among {d} friends. "
             f"How many {obj} does each friend get? {END}")
    return p, q, f"{n} / {d}"


def a_pct_of(rng):
    pct = rng.choice(PCTS)
    if _is_bare("a_pct"):
        base = pct_base(rng, pct)
        p = f"What is {pct}% of {base}? {END}"
    else:
        base = pct_base(rng, pct, max_base=200)
        p = (f"A class has {base} students and {pct}% of them ride the bus. "
             f"How many students ride the bus? {END}")
    d = f"{base} * {pct} / 100"
    return p, base * pct // 100, d


def a_word_2step(rng):
    name = rng.choice(NAMES_A); obj = rng.choice(OBJECTS_A)
    v = rng.randrange(3)
    if v == 0:
        a = rng.randint(2, 9); price = rng.randint(2, 20)
        cost = a * price
        note = next(nt for nt in (50, 100, 200) if cost <= nt)
        p = (f"{name} buys {a} {obj} at {price} dollars each and pays with "
             f"a {note} dollar bill. How much change does {name} get? {END}")
        d = f"{note} - {a} * {price}"
    elif v == 1:
        per = rng.randint(3, 30); days = rng.randint(2, 14)
        total = per * days + rng.randint(5, 200)
        p = (f"{name} reads {per} pages every day. After {days} days, how "
             f"many pages are left in a {total}-page book? {END}")
        d = f"{total} - {per} * {days}"
    else:
        shop = rng.choice(SHOPS_A); price = rng.randint(2, 25)
        a = rng.randint(1, 9); b = rng.randint(1, 9)
        p = (f"A {shop} sells {obj} for {price} dollars each. {name} buys "
             f"{a} on Monday and {b} on Tuesday. How much does {name} "
             f"spend in total? {END}")
        d = f"({a} + {b}) * {price}"
    return p, eval(d), d


def a_unit_price(rng):
    n, total, unit = unit_price_numbers(rng)
    obj = rng.choice(OBJECTS_A)
    if rng.randrange(2) == 0:
        p = (f"{n} {obj} cost {total:.2f} dollars in total. What is the "
             f"cost of one? {END}")
    else:
        name = rng.choice(NAMES_A)
        p = (f"{name} pays {total:.2f} dollars for {n} identical {obj}. "
             f"How much does each one cost? {END}")
    return p, round(unit, 2), f"{total:.2f} / {n}"


def a_compare(rng):
    x = rng.randint(10, 9999); y = rng.randint(10, 9999)
    while y == x:
        y = rng.randint(10, 9999)
    if rng.randrange(2) == 0:
        p = f"Which is larger, {x} or {y}? {END}"
    else:
        p = f"Of the numbers {x} and {y}, which is the greater one? {END}"
    return p, max(x, y), f"max({x}, {y})"


GEN_A = {"addsub_chain": a_addsub_chain, "mul_2x1": a_mul_2x1,
         "mul_2x2": a_mul_2x2, "div_exact": a_div_exact,
         "pct_of": a_pct_of, "word_2step": a_word_2step,
         "unit_price": a_unit_price, "compare": a_compare}

# ================= TEMPLATE SET B (heldout only) =================
# Written as separate code with different surface forms from set A.
# None of the set-A-only marker phrases (see verify_batteries.py) may
# appear in any set-B prompt.

def b_addsub_chain(rng):
    name = rng.choice(NAMES_B); obj = rng.choice(OBJECTS_B)
    if _is_bare("b_addsub"):
        a = rng.randint(100, 9999); b = rng.randint(10, 999)
        c = rng.randint(1, a + b - 1)
        p = f"Calculate: {a} + {b} - {c}. {END}"
        d = f"{a} + {b} - {c}"
    elif rng.randrange(2) == 0:
        a = rng.randint(100, 9999); b = rng.randint(10, 999)
        c = rng.randint(1, a + b - 1)
        p = (f"Beginning from {a}, increase by {b}, then decrease by {c}. "
             f"You finish on which value? {END}")
        d = f"{a} + {b} - {c}"
    else:
        a = rng.randint(50, 999); c = rng.randint(1, a - 1)
        b = rng.randint(10, 500)
        p = (f"{name}'s jar held {a} {obj} on Monday. On Tuesday {name} "
             f"dropped in {b} more, and on Wednesday {name} took out {c}. "
             f"The jar now holds how many {obj}? {END}")
        d = f"{a} + {b} - {c}"
    return p, eval(d), d


def b_mul_2x1(rng):
    a = rng.randint(12, 99); m = rng.randint(2, 9)
    if _is_bare("b_mul_2x1"):
        p = f"Work out {m} lots of {a}. {END}"
        d = f"{m} * {a}"
    else:
        name = rng.choice(NAMES_B); obj = rng.choice(OBJECTS_B)
        p = (f"One crate holds {a} {obj}. {name} stacks {m} such crates. "
             f"The total count of {obj} comes to what? {END}")
        d = f"{a} * {m}"
    return p, a * m, d


def b_mul_2x2(rng):
    a = rng.randint(12, 99); b = rng.randint(12, 99)
    if _is_bare("b_mul_2x2"):
        p = f"{a} * {b} equals what? {END}"
    elif rng.randrange(2) == 0:
        p = (f"A seating grid has {a} rows and {b} seats per row. "
             f"Give the total number of seats. {END}")
    else:
        p = (f"Each of the {a} shelves holds {b} jars. Counting every "
             f"shelf, the jars number how many? {END}")
    d = f"{a} * {b}"
    return p, a * b, d


def b_div_exact(rng):
    d = rng.randint(2, 12); q = rng.randint(3, 99); n = d * q
    if _is_bare("b_div"):
        p = f"{n} / {d} equals what? {END}"
    elif rng.randrange(2) == 0:
        p = (f"{n} litres of water are poured equally into {d} bottles. "
             f"Each bottle receives how many litres? {END}")
    else:
        p = f"Split {n} into {d} equal parts. Each part equals what? {END}"
    return p, q, f"{n} / {d}"


def b_pct_of(rng):
    pct = rng.choice(PCTS)
    if _is_bare("b_pct"):
        base = pct_base(rng, pct)
        p = f"{pct} percent of {base} equals what? {END}"
    elif rng.randrange(2) == 0:
        base = pct_base(rng, pct)
        p = (f"A coat priced at {base} dollars is reduced by {pct} "
             f"percent. The reduction is how many dollars? {END}")
    else:
        base = pct_base(rng, pct, max_base=400)
        p = (f"Out of {base} voters surveyed, {pct} percent preferred "
             f"tea. That share of the voters is how many people? {END}")
    d = f"{base} * {pct} / 100"
    return p, base * pct // 100, d


def b_word_2step(rng):
    # F2b: mirror set A's three subtypes (change, reading-remainder,
    # buy-twice total) in similar proportions, with set-B surfaces.
    name = rng.choice(NAMES_B); obj = rng.choice(OBJECTS_B)
    v = rng.randrange(3)
    if v == 0:
        a = rng.randint(2, 9); price = rng.randint(2, 20)
        cost = a * price
        note = next(nt for nt in (50, 100, 200) if cost <= nt)
        p = (f"{name} hands over a {note} dollar note for {a} {obj} "
             f"costing {price} dollars apiece. The change due is how "
             f"many dollars? {END}")
        d = f"{note} - {a} * {price}"
    elif v == 1:
        per = rng.randint(3, 30); days = rng.randint(2, 14)
        total = per * days + rng.randint(5, 200)
        p = (f"{name} works through a {total}-page novel at {per} "
             f"pages daily. Once {days} days have passed, the pages "
             f"still unread number how many? {END}")
        d = f"{total} - {per} * {days}"
    else:
        shop = rng.choice(SHOPS_B); price = rng.randint(2, 25)
        a = rng.randint(1, 9); b = rng.randint(1, 9)
        p = (f"At the {shop}, {obj} are priced at {price} dollars "
             f"apiece. {name} picks up {a} on Friday and {b} on "
             f"Saturday. Altogether {name} pays how many dollars? "
             f"{END}")
        d = f"({a} + {b}) * {price}"
    return p, eval(d), d


def b_unit_price(rng):
    n, total, unit = unit_price_numbers(rng)
    obj = rng.choice(OBJECTS_B)
    if rng.randrange(2) == 0:
        p = (f"A set of {n} identical {obj} is priced at {total:.2f} "
             f"dollars altogether. A single one costs how many dollars? "
             f"{END}")
    else:
        name = rng.choice(NAMES_B)
        p = (f"For {total:.2f} dollars, {name} bought {n} matching {obj}. "
             f"The price per item is which amount? {END}")
    return p, round(unit, 2), f"{total:.2f} / {n}"


def b_compare(rng):
    # F2a: mirror set A exactly in operation mix -- max-of-two only
    # (no min, no max-of-three), in set-B phrasings.
    x = rng.randint(10, 9999); y = rng.randint(10, 9999)
    while y == x:
        y = rng.randint(10, 9999)
    if rng.randrange(2) == 0:
        p = f"Between {x} and {y}, pick the larger value. {END}"
    else:
        p = (f"Given {x} and {y}, state the maximum of the pair. "
             f"{END}")
    return p, max(x, y), f"max({x}, {y})"


GEN_B = {"addsub_chain": b_addsub_chain, "mul_2x1": b_mul_2x1,
         "mul_2x2": b_mul_2x2, "div_exact": b_div_exact,
         "pct_of": b_pct_of, "word_2step": b_word_2step,
         "unit_price": b_unit_price, "compare": b_compare}

# ================= arithmetic split builder =================

def build_arith_split(split, prefix, seed, per_cat, gens, seen_prompts,
                      seen_derivations=None):
    """per_cat items per category; prompt strings AND derivation
    strings globally unique across all arithmetic splits (F3)."""
    if seen_derivations is None:
        seen_derivations = set()
    rng = random.Random(seed)
    items = []
    n = 0
    for cat in CATEGORIES:
        made = 0
        attempts = 0
        while made < per_cat:
            attempts += 1
            if attempts > 10000:
                raise RuntimeError(f"cannot fill {split}/{cat}")
            prompt, answer, deriv = gens[cat](rng)
            if prompt in seen_prompts or deriv in seen_derivations:
                continue
            seen_prompts.add(prompt)
            seen_derivations.add(deriv)
            n += 1
            items.append({"id": f"{prefix}-{n:03d}", "split": split,
                          "category": cat, "prompt": prompt,
                          "answer": answer, "derivation": deriv})
            made += 1
    return items


# ================= forget_instr =================
# Item: {"id","category","prompt","check":{...}}; category == check type.

INSTR_JSON_KEYS = [
    ("color", "your favourite colour"),
    ("name", "a made-up first name for a pet cat"),
    ("city", "a city you would like to visit"),
    ("food", "your favourite food"),
    ("sport", "a sport played with a ball"),
    ("animal", "an animal that lives in the sea"),
    ("season", "your favourite season of the year"),
    ("drink", "a hot drink"),
    ("flower", "a kind of flower"),
    ("job", "a job that involves working outdoors"),
    ("fruit", "a fruit that is yellow"),
    ("vehicle", "a vehicle with two wheels"),
    ("instrument", "a musical instrument"),
    ("country", "a country in Europe"),
    ("hobby", "a hobby you can do indoors"),
    ("weather", "a word describing today's weather"),
    ("book", "a made-up title for an adventure book"),
]

INSTR_CAPS_PHRASES = [
    "good morning", "thank you very much", "see you later", "the cat sat",
    "it is raining today", "please sit down", "happy birthday to you",
    "the train is late", "dinner is ready", "i love pizza", "open the door",
    "the sky is blue", "we are going home", "this is a test",
    "the dog is happy", "read the book", "the water is cold",
]

INSTR_START_WORDS = [
    ("The", "the sea"), ("Today", "the weather"), ("My", "a pet you know"),
    ("In", "a small village"), ("When", "a rainy day"),
    ("Under", "a tall tree"), ("Every", "a morning routine"),
    ("After", "a long journey"), ("The", "a busy market"),
    ("Once", "a clever fox"), ("Near", "a quiet river"),
    ("During", "the winter season"), ("With", "a good friend"),
    ("Behind", "an old house"), ("Across", "a wide field"),
    ("Before", "breakfast time"), ("Along", "a sandy beach"),
]

INSTR_END_WORDS = [
    ("home", "walking back"), ("today", "your plans"),
    ("soon", "a friend arriving"), ("tonight", "the evening sky"),
    ("outside", "playing games"), ("together", "cooking a meal"),
    ("again", "visiting a favourite place"), ("tomorrow", "the weekend"),
    ("slowly", "a river flowing"), ("quietly", "sitting in a library"),
    ("well", "a day of hard work"), ("far", "a journey on foot"),
    ("early", "waking up on holiday"), ("back", "returning from a trip"),
    ("free", "a bird in the sky"), ("bright", "the morning sun"),
    ("away", "a kite in the wind"),
]

INSTR_BULLET_TOPICS = [
    "three fruits", "three colours", "three animals",
    "three things found in a kitchen", "three sports",
    "three things you can drink", "three vegetables",
    "three things found at the beach", "three musical instruments",
    "three things that can fly", "three items of clothing",
    "three things in a garden", "three kinds of transport",
    "three things made of wood", "three breakfast foods",
    "three things that are cold", "three rooms in a house",
]

INSTR_WORDCOUNT_TOPICS = [
    ("a cat", 5, 10), ("a rainy day", 6, 12), ("a bicycle", 5, 9),
    ("your breakfast", 4, 8), ("a tall tree", 5, 10), ("the moon", 6, 11),
    ("a cup of tea", 4, 9), ("a small boat", 5, 10), ("a garden", 6, 12),
    ("a friendly dog", 5, 9), ("snow in winter", 4, 8),
    ("a busy train station", 6, 12), ("a slice of cake", 5, 10),
    ("a mountain path", 6, 11), ("a quiet library", 5, 10),
    ("a summer evening", 4, 9), ("a red kite", 5, 8),
]


def build_forget_instr(seed):
    rng = random.Random(seed)
    pools = {
        "json_key": [
            (f'Reply with a JSON object that has a key "{k}" whose value '
             f'is {v}.', {"type": "json_key", "key": k})
            for k, v in INSTR_JSON_KEYS],
        "all_caps": [
            (f"Write the phrase \"{p}\" in all capital letters.",
             {"type": "all_caps"})
            for p in INSTR_CAPS_PHRASES],
        "starts_with": [
            (f'Write one sentence about {t} that starts with the word '
             f'"{w}".', {"type": "starts_with", "word": w})
            for w, t in INSTR_START_WORDS],
        "ends_with": [
            (f'Write one sentence about {t} that ends with the word '
             f'"{w}".', {"type": "ends_with", "word": w})
            for w, t in INSTR_END_WORDS],
        "bullets3": [
            (f"List {t}, one per line, with each line starting "
             f"with \"- \".", {"type": "bullets3"})
            for t in INSTR_BULLET_TOPICS],
        "word_count_range": [
            (f"Describe {t} in between {lo} and {hi} words.",
             {"type": "word_count_range", "lo": lo, "hi": hi})
            for t, lo, hi in INSTR_WORDCOUNT_TOPICS],
    }
    for pool in pools.values():
        rng.shuffle(pool)
    types = list(pools.keys())
    items = []
    # 100 items: cycle check types, drawing without repetition per type.
    idx = {t: 0 for t in types}
    for i in range(100):
        t = types[i % len(types)]
        prompt, check = pools[t][idx[t] % len(pools[t])]
        idx[t] += 1
        items.append({"id": f"finstr-{i + 1:03d}", "category": t,
                      "prompt": prompt, "check": check})
    return items

# ================= forget_fact (fixed tables) =================
# (prompt, answer, aliases)

CAPITALS = [
    ("What is the capital of France?", "Paris", []),
    ("What is the capital of Japan?", "Tokyo", []),
    ("What is the capital of Australia?", "Canberra", []),
    ("What is the capital of Canada?", "Ottawa", []),
    ("What is the capital of Brazil?", "Brasilia", ["Brasília"]),
    ("What is the capital of Egypt?", "Cairo", []),
    ("What is the capital of India?", "New Delhi", ["Delhi"]),
    ("What is the capital of Spain?", "Madrid", []),
    ("What is the capital of Italy?", "Rome", []),
    ("What is the capital of Germany?", "Berlin", []),
    ("What is the capital of Norway?", "Oslo", []),
    ("What is the capital of Sweden?", "Stockholm", []),
    ("What is the capital of Finland?", "Helsinki", []),
    ("What is the capital of Poland?", "Warsaw", []),
    ("What is the capital of Greece?", "Athens", []),
    ("What is the capital of Turkey?", "Ankara", []),
    ("What is the capital of Mexico?", "Mexico City", []),
    ("What is the capital of Argentina?", "Buenos Aires", []),
    ("What is the capital of Chile?", "Santiago", []),
    ("What is the capital of Peru?", "Lima", []),
    ("What is the capital of Kenya?", "Nairobi", []),
    ("What is the capital of Iceland?", "Reykjavik", ["Reykjavík"]),
    ("What is the capital of Ireland?", "Dublin", []),
    ("What is the capital of Portugal?", "Lisbon", []),
    ("What is the capital of Austria?", "Vienna", []),
    ("What is the capital of Switzerland?", "Bern", ["Berne"]),
    ("What is the capital of the Netherlands?", "Amsterdam", []),
    ("What is the capital of Denmark?", "Copenhagen", []),
    ("What is the capital of New Zealand?", "Wellington", []),
    ("What is the capital of South Korea?", "Seoul", []),
]

ELEMENTS = [
    ("What is the chemical symbol for gold?", "Au", []),
    ("What is the chemical symbol for oxygen?", "O", []),
    ("What is the chemical symbol for hydrogen?", "H", []),
    ("What is the chemical symbol for iron?", "Fe", []),
    ("What is the chemical symbol for silver?", "Ag", []),
    ("What is the chemical symbol for sodium?", "Na", []),
    ("What is the chemical symbol for potassium?", "K", []),
    ("What is the chemical symbol for calcium?", "Ca", []),
    ("What is the chemical symbol for carbon?", "C", []),
    ("What is the chemical symbol for nitrogen?", "N", []),
    ("What is the chemical symbol for helium?", "He", []),
    ("What is the chemical symbol for lead?", "Pb", []),
    ("What is the chemical symbol for copper?", "Cu", []),
    ("What is the chemical symbol for zinc?", "Zn", []),
    ("What is the chemical symbol for aluminium?", "Al", []),
    ("What is the chemical symbol for sulphur?", "S", []),
    ("What is the chemical symbol for chlorine?", "Cl", []),
    ("What is the chemical symbol for magnesium?", "Mg", []),
    ("What is the chemical symbol for silicon?", "Si", []),
    ("What is the chemical symbol for phosphorus?", "P", []),
    ("What is the chemical symbol for mercury?", "Hg", []),
    ("What is the chemical symbol for tin?", "Sn", []),
    ("What is the chemical symbol for neon?", "Ne", []),
    ("What is the chemical symbol for lithium?", "Li", []),
    ("What is the chemical symbol for boron?", "B", []),
]

SOLAR = [
    ("Which planet is known as the Red Planet?", "Mars", []),
    ("Which planet is closest to the Sun?", "Mercury", []),
    ("Which is the largest planet in our solar system?", "Jupiter", []),
    ("Which planet has prominent rings around it?", "Saturn", []),
    ("How many moons does Earth have?", "1", []),
    ("Which planet do we live on?", "Earth", []),
    ("What is the name of the star at the centre of our solar system?",
     "the Sun", ["Sun"]),
    ("Which planet is known as the Morning Star?", "Venus", []),
    ("Which dwarf planet was once counted as the ninth planet?",
     "Pluto", []),
    ("Which planet is farthest from the Sun?", "Neptune", []),
    ("What is Earth's only natural satellite called?", "the Moon",
     ["Moon"]),
    ("Which planet has the longest day, longer than its year?",
     "Venus", []),
    ("Which planet spins on its side, tilted almost 98 degrees?",
     "Uranus", []),
    ("Which moon of Jupiter is covered in ice and may hide an ocean?",
     "Europa", []),
    ("What is the name of the galaxy that contains our solar system?",
     "the Milky Way", ["Milky Way"]),
]

CONVERSIONS = [
    ("How many centimetres are there in one metre?", "100",
     ["100 cm"]),
    ("How many grams are there in one kilogram?", "1000",
     ["1000 g", "1,000"]),
    ("How many minutes are there in one hour?", "60", ["60 minutes"]),
    ("How many seconds are there in one minute?", "60",
     ["60 seconds"]),
    ("How many hours are there in one day?", "24", ["24 hours"]),
    ("How many days are there in one week?", "7", ["7 days"]),
    ("How many months are there in one year?", "12", ["12 months"]),
    ("How many millimetres are there in one centimetre?", "10",
     ["10 mm"]),
    ("How many metres are there in one kilometre?", "1000",
     ["1000 m", "1,000"]),
    ("How many millilitres are there in one litre?", "1000",
     ["1000 ml", "1,000"]),
    ("How many degrees are there in a right angle?", "90",
     ["90 degrees"]),
    ("How many degrees are there in a full circle?", "360",
     ["360 degrees"]),
    ("How many cents are there in one dollar?", "100", ["100 cents"]),
    ("How many years are there in a decade?", "10", ["ten"]),
]

MISC = [
    ("What is the largest ocean on Earth?", "Pacific Ocean",
     ["Pacific"]),
    ("What is the longest river in the world?", "the Nile", ["Nile"]),
    ("What is the tallest land animal?", "giraffe", ["a giraffe"]),
    ("How many legs does a spider have?", "8", ["eight"]),
    ("What is the fastest land animal?", "cheetah", ["a cheetah"]),
    ("Which continent is the Sahara Desert on?", "Africa", []),
    ("What is the largest mammal in the world?", "blue whale",
     ["a blue whale"]),
    ("How many hearts does an octopus have?", "3", ["three"]),
    ("What is the main language spoken in Brazil?", "Portuguese", []),
    ("Which bird is a symbol of peace?", "dove", ["a dove"]),
    ("What do bees produce?", "honey", []),
    ("What is the largest hot desert in the world?", "the Sahara",
     ["Sahara"]),
    ("How many wings does a butterfly have?", "4", ["four"]),
    ("What is the capital city of the United Kingdom?", "London", []),
    ("Which animal is known as man's best friend?", "dog", ["a dog"]),
    ("How many sides does a hexagon have?", "6", ["six"]),
]

FACT_TABLES = [("capitals", CAPITALS), ("elements", ELEMENTS),
               ("solar_system", SOLAR), ("conversions", CONVERSIONS),
               ("misc", MISC)]


def build_forget_fact(seed):
    rng = random.Random(seed)
    items = []
    n = 0
    for cat, table in FACT_TABLES:
        rows = list(table)
        rng.shuffle(rows)
        for prompt, answer, aliases in rows:
            n += 1
            items.append({"id": f"ffact-{n:03d}", "category": cat,
                          "prompt": prompt, "answer": answer,
                          "aliases": aliases})
    return items

# ================= forget_prose (inline paragraphs) =================

PROSE = [
    "The harbour woke slowly, with gulls circling above the moored boats "
    "and the smell of salt drifting across the quiet water. Fishermen "
    "moved along the wooden pier carrying crates and coiled ropes, their "
    "boots thudding softly in the grey light. Beyond the breakwater the "
    "sea lay flat and silver, and a single buoy bell sounded at long "
    "intervals. In the small cafe by the ramp, someone switched on the "
    "lights and began setting out cups for the first customers.",

    "The old library stood at the corner of the street, its stone steps "
    "worn smooth by generations of readers. Inside, tall shelves rose "
    "toward a ceiling painted with faded stars, and the air carried the "
    "dry, sweet smell of paper and polish. A librarian pushed a trolley "
    "of returned books between the tables, pausing now and then to "
    "straighten a chair or glance at a title. Rain began to tap gently "
    "against the high windows as the afternoon settled in.",

    "A narrow path wound through the meadow, bordered by tall grass and "
    "the occasional flat stone warmed by the sun. Butterflies drifted "
    "above the wildflowers, and somewhere in the hedge a blackbird "
    "repeated its short, bright phrase. The walker carried nothing but "
    "a canvas bag and a bottle of water, content to follow the path "
    "wherever it chose to bend. By the time the church tower appeared "
    "above the trees, the light had turned the colour of honey.",

    "The workshop smelled of cedar shavings and machine oil. Along one "
    "wall, hand tools hung in a neat row above the bench, each outlined "
    "in pencil where it belonged. A half-finished chair stood in the "
    "middle of the room, one leg still rough, waiting for the plane. "
    "Through the open door came the sounds of the street: a bicycle "
    "bell, distant voices, the rumble of a passing cart. The craftsman "
    "worked steadily, measuring twice before every cut.",

    "Snow had fallen overnight, softening the edges of the rooftops and "
    "fences along the lane. Smoke rose straight from the chimneys into "
    "a pale, windless sky. Children dragged sledges toward the hill "
    "behind the school, their breath making small clouds in the cold "
    "air. The baker opened his shop early, and the smell of warm bread "
    "drifted out each time the door swung. By noon, footprints crossed "
    "the white fields in every direction.",

    "The train followed the coast for the last hour of the journey, the "
    "sea appearing and disappearing between cuttings and small stations. "
    "Passengers read newspapers, slept with their coats folded under "
    "their heads, or watched the waves through salt-flecked windows. At "
    "every stop, the guard stepped down onto the platform and called "
    "out the name of the place in a clear, practised voice. When the "
    "town finally came into view, people began gathering their bags.",

    "In the botanical garden, paths of pale gravel led between beds of "
    "labelled plants from every climate. The glasshouse held a warm, "
    "damp air and the slow drip of water onto broad leaves. An elderly "
    "gardener pruned the roses with unhurried care, dropping the "
    "cuttings into a woven basket. Visitors spoke in low voices, as "
    "people often do among plants, and a child pressed her face to the "
    "glass to watch the goldfish in the lily pond.",

    "The market square filled gradually on Saturday morning, stall by "
    "stall, awning by awning. Farmers arranged apples in pyramids and "
    "laid out cheeses wrapped in cloth. The flower seller arranged "
    "buckets of tulips by colour, red beside yellow beside white. A "
    "musician tuned his fiddle near the fountain, more for his own "
    "pleasure than for an audience. By ten o'clock the square was "
    "crowded, and the air smelled of coffee, strawberries, and rain "
    "that had not yet fallen.",

    "High on the moor, the wind moved through the heather in long, "
    "visible waves. A single track of pale stones crossed the plateau "
    "toward a ruined shepherd's hut, its roof long gone. Sheep watched "
    "the walker pass with calm indifference before returning to their "
    "grazing. Clouds travelled quickly overhead, and their shadows "
    "raced across the slopes faster than any animal could run. It was "
    "a place that asked little of visitors except that they keep "
    "walking and pay attention.",

    "The ferry crossed the river every twenty minutes, carrying "
    "shoppers, cyclists, and the occasional horse. Its engine beat a "
    "slow rhythm against the current while the ferryman leaned on the "
    "rail and exchanged news with passengers he had known for years. "
    "On the far bank, willow trees trailed their branches in the "
    "water, and a heron stood motionless in the shallows. The crossing "
    "took only a few minutes, yet it always felt like a small holiday "
    "from the road.",

    "Behind the farmhouse, the orchard sloped gently down to a stone "
    "wall covered in moss. The apple trees were old and irregular, "
    "their branches propped with forked sticks in heavy years. In "
    "spring the whole slope turned white with blossom, and bees worked "
    "from tree to tree in a steady hum. Now, in late summer, the first "
    "fallen apples dotted the grass, and wasps gathered around them in "
    "the warm afternoon air.",

    "The lighthouse stood on a point of black rock, painted in bands of "
    "white and red. Its lamp room caught the evening sun long after "
    "the shore below had fallen into shadow. The keeper climbed the "
    "spiral stair each dusk, checked the lamp and the logbook, and "
    "made a pot of tea in the small round kitchen. From the gallery, "
    "the sea stretched away to a horizon so sharp it seemed drawn "
    "with a ruler.",

    "A quiet street of brick houses ran down toward the canal, each "
    "front garden enclosed by a low iron railing. Cats slept on warm "
    "doorsteps, and window boxes overflowed with geraniums. At the "
    "corner, a small bookshop kept its door propped open with a "
    "painted stone. In the evenings, the lamplighter's modern successor "
    "was only a timer in a cabinet, yet the lamps still came on one "
    "by one, as if lit by hand, all the way down the hill.",

    "The valley river ran clear over stones the colour of rust and "
    "grey. Trout held station in the deeper pools, facing upstream, "
    "barely moving except for the slow fan of their tails. Along the "
    "banks, alder roots reached into the water, and kingfishers were "
    "said to nest in the soft earth above the bend. After rain, the "
    "river rose quickly, carrying branches and foam, but by the next "
    "morning it would be clear and unhurried again.",

    "Inside the station, the departures board clicked and refreshed "
    "itself with a soft mechanical sigh. Travellers studied it with "
    "the particular patience of people who have nowhere better to be "
    "for the next ten minutes. A cleaner guided her machine in slow "
    "arcs across the concourse, and the smell of floor polish mixed "
    "with coffee from the kiosk. Pigeons walked in and out of the "
    "great doorway as if they owned shares in the building.",

    "The pottery studio occupied a converted barn at the end of a "
    "farm track. Wheels turned in a row by the windows, and shelves "
    "of glazed bowls caught the light in blues and greens. The potter "
    "worked with sleeves rolled and hands grey with clay, centring "
    "each lump with a few sure movements. Finished pieces cooled on "
    "boards near the kiln, waiting for the firing that would fix "
    "their colours and test every join.",

    "Autumn came to the forest in patches, a single beech turning gold "
    "while its neighbours stayed green. Fallen leaves softened the "
    "rides and muffled the sound of hooves on the morning patrols. "
    "Fungi appeared overnight in the damp hollows: red caps, pale "
    "fans, and clusters of small brown umbrellas along the rotting "
    "logs. The air smelled of earth and woodsmoke, and by four "
    "o'clock the light was already leaving the valley floor.",

    "The observatory dome sat above the town on a hill of short grass "
    "and scattered pines. On clear nights, the slit opened and the "
    "great telescope swung silently toward its target. The astronomer "
    "kept notes in a leather book, in handwriting that had not changed "
    "in thirty years. Visitors who climbed the hill for the open "
    "evenings remembered less about the planets than about the cold, "
    "the darkness, and the slow wheeling of the stars.",

    "Along the towpath, narrowboats were moored in a line of bright "
    "paintwork and polished brass. Smoke curled from small chimneys, "
    "and the smell of coal and cooking drifted across the water. A "
    "woman watered the flower boxes on her cabin roof while a dog "
    "watched the ducks with professional interest. The lock keeper "
    "leaned on the beam, in no hurry at all, as the water level rose "
    "and the gates prepared to open.",

    "The clockmaker's shop was narrow and dim, filled with the "
    "competing ticking of a hundred clocks. Cases of polished wood "
    "lined the walls, and a cat slept undisturbed on the counter "
    "beside the till. The clockmaker bent over an open movement with "
    "tweezers and a magnifier, breathing slowly, entirely absorbed. "
    "Customers learned to wait without impatience; time, in that shop, "
    "was clearly in professional hands and would be attended to in "
    "due course.",

    "At the edge of the salt marsh, the path ran along a low sea wall "
    "of packed earth and stone. Samphire grew in the mud below, and "
    "at high tide the channels filled into a shining sheet of water "
    "that mirrored the sky. Wading birds probed the edges with long "
    "bills, rising in small flocks when a walker came too near. The "
    "wind carried the clean, mineral smell of the estuary for miles "
    "inland.",

    "The village hall had hosted dances, elections, weddings, and "
    "one memorable flood sale in its ninety years. Its noticeboard "
    "layered poster over poster until the cork was an archaeology of "
    "local life. On Tuesdays, the badminton club set up its net and "
    "argued cheerfully about the score. The caretaker arrived early "
    "to put the chairs out in rows, counting them aloud out of habit, "
    "though he had known the number by heart for decades.",

    "A greenhouse of misted glass stood behind the nursery, where "
    "rows of young plants waited in ordered trays. The air inside "
    "was warm and green-smelling, and water dripped steadily from "
    "the overhead lines. Gardeners moved along the rows with "
    "clipboards, noting which seedlings were ready to move outside. "
    "Outside, the fields stretched in long, dark lines of turned "
    "earth, ready for planting as soon as the weather gave the word.",

    "The coastal path climbed from the village in a series of "
    "zigzags, each turn opening a wider view of the bay. Gorse "
    "burned yellow along the edges, and the grass was cropped short "
    "by rabbits and the constant wind. Far below, the harbour "
    "collected its boats into a neat crescent of masts and coloured "
    "hulls. Walkers coming down greeted those going up with the "
    "special cheerfulness of people who have already seen what lies "
    "at the top.",
]


def build_forget_prose():
    assert len(PROSE) == 24, len(PROSE)
    items = []
    for i, text in enumerate(PROSE):
        wc = len(text.split())
        assert 60 <= wc <= 90, f"prose {i + 1} has {wc} words"
        items.append({"id": f"fprose-{i + 1:03d}", "text": text})
    return items


def write_jsonl(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def main():
    assert [len(t) for _, t in FACT_TABLES] == [30, 25, 15, 14, 16]
    seen = set()
    seen_derivations = set()
    diag = build_arith_split("diagnostic", "diag", SEED_DIAGNOSTIC,
                             10, GEN_A, seen, seen_derivations)
    val = build_arith_split("validation", "val", SEED_VALIDATION,
                            25, GEN_A, seen, seen_derivations)
    held = build_arith_split("heldout", "held", SEED_HELDOUT,
                             25, GEN_B, seen, seen_derivations)
    instr = build_forget_instr(SEED_INSTR)
    fact = build_forget_fact(SEED_FACT)
    prose = build_forget_prose()
    assert len(diag) == 80 and len(val) == 200 and len(held) == 200
    assert len(instr) == 100 and len(fact) == 100 and len(prose) == 24
    # N3: emit the full set-A marker list for the verifier.
    markers = {
        "pool_a": {"names": NAMES_A, "objects": OBJECTS_A,
                   "shops": SHOPS_A},
        "template_frames_a": SET_A_FRAGMENTS,
        "markers": (NAMES_A + OBJECTS_A + SHOPS_A
                    + SET_A_FRAGMENTS),
    }
    (HERE / "batteries" / "setA_markers.json").write_text(
        json.dumps(markers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    write_jsonl(HERE / "batteries" / "diagnostic.jsonl", diag)
    write_jsonl(HERE / "batteries" / "validation.jsonl", val)
    write_jsonl(HERE / "private" / "heldout.jsonl", held)
    write_jsonl(HERE / "private" / "forget_instr.jsonl", instr)
    write_jsonl(HERE / "private" / "forget_fact.jsonl", fact)
    write_jsonl(HERE / "private" / "forget_prose.jsonl", prose)
    for name, items in [("diagnostic", diag), ("validation", val),
                        ("heldout", held), ("forget_instr", instr),
                        ("forget_fact", fact), ("forget_prose", prose)]:
        print(f"{name}: {len(items)} items")


if __name__ == "__main__":
    main()
