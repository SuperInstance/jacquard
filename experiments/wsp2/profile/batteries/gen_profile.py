#!/usr/bin/env python3
"""Generator for the Jacquard patchability-profile battery suite.

Six grades in boundary order (see ../README.md and
experiments/wsp2/CRITERIA.md R2):
  G1 format/completion, G2 framing, G3 readout, G4 procedure,
  G5 factor-knowledge, G6 unseparated relation.

Discipline inherited from Phase 15 (experiments/wsp/gen_batteries*.py):
  - seeded, deterministic (Python stdlib random only); regeneration
    with the same code is byte-identical;
  - splits are disjoint BY CONSTRUCTION: lexical pools are partitioned
    per split, and a global seen-set deduplicates prompt AND
    derivation strings across every split of every grade;
  - golds are computed by construction (datetime / arithmetic /
    explicit authored fact tables), never by a model;
  - held-out items are generated mechanically from templates and
    tables. No item in any split was tuned against a model's output.

Item shape: {"id", "grade", "split", "category", "prompt", "answer",
             "derivation", ...} -- answer is a STRING; scoring is
exact normalised-answer matching (see run_profile.py).

Run:  python3 gen_profile.py            (writes *.jsonl next to itself)
"""
import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPLITS = ["diagnostic", "validation", "heldout"]
SEED = {"G1": 16101, "G2": 16201, "G3": 16301,
        "G4": 16401, "G5": 16501, "G6": 16601}
SPLIT_SALT = {"diagnostic": 0, "validation": 1000, "heldout": 2000}
TARGET = {"diagnostic": 120, "validation": 60, "heldout": 120}

SEEN_PROMPTS = set()
SEEN_DERIVS = set()
SEEN_KEYS = set()


def emit(items, grade, split, category, prompt, answer, derivation,
         key=None, **extra):
    """Append an item if globally unique; return True if appended.

    `key` is an optional canonical content key (e.g. the sorted
    operand pair of an addition): two items sharing a key are
    near-duplicates even when their surface order differs, so the
    second is rejected wherever it appears."""
    if prompt in SEEN_PROMPTS or derivation in SEEN_DERIVS:
        return False
    if key is not None and key in SEEN_KEYS:
        return False
    SEEN_PROMPTS.add(prompt)
    SEEN_DERIVS.add(derivation)
    if key is not None:
        SEEN_KEYS.add(key)
    it = {"id": f"{grade.lower()}-{split[:4]}-{len(items) + 1:03d}",
          "grade": grade, "split": split, "category": category,
          "prompt": prompt, "answer": str(answer),
          "derivation": derivation}
    it.update(extra)
    items.append(it)
    return True


def fill(items, grade, split, gens, target):
    """Round-robin over category generators until target reached."""
    rng_fail = 0
    while len(items) < target:
        progressed = False
        for g in gens:
            if len(items) >= target:
                break
            if g():
                progressed = True
        if not progressed:
            rng_fail += 1
            if rng_fail > 50:
                raise RuntimeError(f"{grade}/{split}: pool exhausted at "
                                   f"{len(items)}/{target}")
    return items


# =====================================================================
# G1 -- format/completion: the knowledge is trivial; only the output
# contract can fail. Categories: copy_token, small_add, seq_next,
# yes_no_compare, last_word.
# =====================================================================
G1_WORDS = {
    "diagnostic": ["lantern", "harbour", "meadow", "copper", "velvet",
                   "saddle", "quiver", "timber", "walnut", "cinder",
                   "plover", "mantle", "sorrel", "tundra", "vesper",
                   "willow", "zephyr", "cobalt", "dorsal", "ember"],
    "validation": ["falcon", "garnet", "hollow", "inkwell", "juniper",
                   "kestrel", "lagoon", "magnet", "nectar", "onyx"],
    "heldout": ["pastel", "quarry", "riddle", "summit", "tapestry",
                "umber", "violet", "wander", "yonder", "zenith",
                "bramble", "cricket", "dapple", "fjord", "glacier",
                "hemlock", "isthmus", "jasmine", "kindle", "lattice"],
}
G1_PAIRS = {  # ABAB sequence word pairs, partitioned per split
    "diagnostic": [("oak", "pine"), ("red", "gold"), ("north", "south"),
                   ("cat", "dog"), ("sun", "moon")],
    "validation": [("king", "queen"), ("day", "night"), ("land", "sea")],
    "heldout": [("iron", "steel"), ("rain", "snow"), ("rock", "sand"),
                ("wolf", "fox"), ("salt", "sugar")],
}
G1_SENTS = {
    "diagnostic": ["The boat left the harbour at dawn",
                   "A cold wind crossed the dark field",
                   "She kept the letter inside the book",
                   "The train stopped beside the river",
                   "He counted the coins on the table"],
    "validation": ["The market opened before the bell",
                   "A grey cat slept under the porch",
                   "They walked home through the snow"],
    "heldout": ["The lighthouse flashed across the bay",
                "An old map hung above the desk",
                "The children planted seeds in spring",
                "His voice echoed down the hall",
                "The kettle sang on the stove"],
}


def gen_g1(split):
    rng = random.Random(SEED["G1"] + SPLIT_SALT[split])
    items = []
    words = list(G1_WORDS[split]); rng.shuffle(words)
    pairs = list(G1_PAIRS[split])
    sents = list(G1_SENTS[split])

    def copy_token():
        if not words:
            return False
        w = words.pop()
        return emit(items, "G1", split, "copy_token",
                    f'Copy this word exactly: "{w}". Answer with just the word.',
                    w, f"copy({w})")

    def small_add():
        a, b = rng.randint(2, 19), rng.randint(2, 19)
        return emit(items, "G1", split, "small_add",
                    f"What is {a} + {b}? Answer with just the number.",
                    a + b, f"{a} + {b}", key=("add", min(a, b), max(a, b)))

    def seq_next():
        kind = rng.randrange(3)
        if kind == 0 and pairs:
            x, y = pairs[rng.randrange(len(pairs))]
            return emit(items, "G1", split, "seq_next",
                        f"What word comes next in this sequence: {x}, {y}, "
                        f"{x}, {y}, {x}, ...? Answer with just the word.",
                        y, f"abab({x},{y})")
        start, step = rng.randint(1, 30), rng.choice([2, 3, 5])
        seq = [start + step * i for i in range(4)]
        return emit(items, "G1", split, "seq_next",
                    f"What number comes next in this sequence: "
                    f"{', '.join(map(str, seq))}, ...? "
                    f"Answer with just the number.",
                    seq[-1] + step, f"seq({start},+{step})")

    def yes_no_compare():
        a, b = rng.randint(2, 99), rng.randint(2, 99)
        if a == b:
            return False
        if rng.random() < 0.5:
            return emit(items, "G1", split, "yes_no_compare",
                        f"Is {a} greater than {b}? Answer yes or no.",
                        "yes" if a > b else "no", f"gt({a},{b})",
                        key=("cmp", min(a, b), max(a, b)))
        return emit(items, "G1", split, "yes_no_compare",
                    f"Is {a} less than {b}? Answer yes or no.",
                    "yes" if a < b else "no", f"lt({a},{b})",
                    key=("cmp", min(a, b), max(a, b)))

    def last_word():
        if not sents:
            return False
        s = sents.pop()
        return emit(items, "G1", split, "last_word",
                    f'What is the last word of this sentence: "{s}." '
                    f"Answer with just the word.",
                    s.split()[-1], f"lastword({s.split()[-1]})")

    return fill(items, "G1", split,
                [copy_token, small_add, seq_next, yes_no_compare, last_word],
                TARGET[split])


# =====================================================================
# G2 -- framing: G1-level content under framing that misleads --
# negation, false claims, distractor facts, quoted questions, order.
# =====================================================================
G2_SETS = {  # (odd-one-out category sets), partitioned per split
    "diagnostic": [("colour", ["red", "blue", "chair", "green"]),
                   ("fruit", ["apple", "pear", "stone", "plum"]),
                   ("animal", ["horse", "goat", "table", "sheep"]),
                   ("vehicle", ["bus", "train", "cloud", "boat"]),
                   ("furniture", ["desk", "lamp", "river", "chair"])],
    "validation": [("metal", ["iron", "copper", "paper", "tin"]),
                   ("bird", ["crow", "finch", "frog", "hawk"]),
                   ("tool", ["hammer", "saw", "apple", "drill"])],
    "heldout": [("vegetable", ["carrot", "pea", "shoe", "onion"]),
                ("instrument", ["flute", "drum", "brick", "cello"]),
                ("planet", ["Mars", "Venus", "Ocean", "Jupiter"]),
                ("sport", ["tennis", "golf", "bread", "rowing"]),
                ("gem", ["ruby", "opal", "wool", "pearl"])],
}
G2_PEOPLE = {
    "diagnostic": [("Jon", "dogs", 3, "fish", 7, 40),
                   ("Ana", "cats", 2, "birds", 5, 31),
                   ("Leo", "bikes", 4, "kites", 6, 22),
                   ("Mia", "hens", 8, "goats", 3, 35),
                   ("Sam", "boats", 2, "cars", 9, 47)],
    "validation": [("Eve", "dogs", 5, "fish", 4, 29),
                   ("Tom", "cats", 6, "hens", 2, 51),
                   ("Zoe", "bikes", 3, "boats", 7, 26)],
    "heldout": [("Max", "horses", 4, "dogs", 6, 44),
                ("Ivy", "ducks", 9, "cats", 3, 33),
                ("Ben", "goats", 5, "bikes", 8, 58),
                ("Amy", "fish", 7, "birds", 4, 27),
                ("Dan", "cars", 3, "kites", 5, 39)],
}
G2_NAMES = {"diagnostic": ["Maria", "Peter", "Lucy", "Omar", "Nina"],
            "validation": ["Karl", "Ruth", "Hugo"],
            "heldout": ["Tara", "Ivan", "Elif", "Rosa", "Finn"]}


def gen_g2(split):
    rng = random.Random(SEED["G2"] + SPLIT_SALT[split])
    items = []
    sets = list(G2_SETS[split]); rng.shuffle(sets)
    people = list(G2_PEOPLE[split])
    names = list(G2_NAMES[split])

    def not_item():
        if not sets:
            return False
        cat, opts = sets.pop()
        # the odd one out is the authored non-member: by construction
        # it is the entry at index 2 of each table row.
        odd_word = opts[2]
        listed = ", ".join(opts)
        art = "an" if cat[0] in "aeiou" else "a"
        return emit(items, "G2", split, "not_category",
                    f"Which of these is NOT {art} {cat}: {listed}? "
                    f"Answer with just the word.",
                    odd_word, f"not({cat},{odd_word})")

    def false_claim():
        a, b = rng.randint(3, 60), rng.randint(3, 60)
        if a == b:
            return False
        name = names[rng.randrange(len(names))]
        claim_true = a > b
        return emit(items, "G2", split, "false_claim",
                    f"{name} says {a} is greater than {b}. "
                    f"Is {name} right? Answer yes or no.",
                    "yes" if claim_true else "no", f"claim({a}>{b})",
                    key=("cmp", min(a, b), max(a, b)))

    def distractor():
        if not people:
            return False
        name, thing, n, other, m, age = people.pop()
        return emit(items, "G2", split, "distractor",
                    f"{name} has {n} {thing} and {m} {other}. "
                    f"{name} is {age} years old. How many {thing} does "
                    f"{name} have? Answer with just the number.",
                    n, f"distract({name},{thing})")

    def quoted():
        a, b = rng.randint(3, 29), rng.randint(3, 29)
        name = names[rng.randrange(len(names))]
        return emit(items, "G2", split, "quoted_question",
                    f'{name} asks: "What is {a} + {b}?" '
                    f"Answer with just the number.",
                    a + b, f"quoted({a}+{b})",
                    key=("add", min(a, b), max(a, b)))

    def order_swap():
        a, b = rng.randint(3, 99), rng.randint(3, 99)
        if a == b:
            return False
        return emit(items, "G2", split, "order_swap",
                    f"Answer yes or no: is {a} less than {b}?",
                    "yes" if a < b else "no", f"swaplt({a},{b})",
                    key=("cmp", min(a, b), max(a, b)))

    return fill(items, "G2", split,
                [not_item, false_claim, distractor, quoted, order_swap],
                TARGET[split])


# =====================================================================
# G3 -- readout: surface properties the representation plainly
# carries; the only work is reading the property out under the
# stated label set. Golds computed from the word/sentence itself.
# =====================================================================
G3_WORDS = {
    "diagnostic": ["apple", "bridge", "orange", "table", "umbrella",
                   "window", "island", "pencil", "ocean", "garden",
                   "engine", "bottle", "anchor", "school", "igloo",
                   "market", "olive", "rabbit", "uncle", "stone"],
    "validation": ["eagle", "hammer", "onion", "ladder", "apron",
                   "cabin", "idea", "forest", "oven", "tulip"],
    "heldout": ["arrow", "basket", "elbow", "mirror", "ostrich",
                "pillow", "avenue", "candle", "insect", "harvest",
                "opera", "jungle", "unit", "saddle", "echo",
                "village", "onset", "ribbon", "atom", "meadow"],
}
G3_PLURALS = {  # (singular, plural) pairs, partitioned
    "diagnostic": [("goose", "geese"), ("child", "children"),
                   ("foot", "feet"), ("man", "men"), ("mouse", "mice")],
    "validation": [("tooth", "teeth"), ("woman", "women"),
                   ("ox", "oxen")],
    "heldout": [("leaf", "leaves"), ("wolf", "wolves"),
                ("person", "people"), ("die", "dice"),
                ("cactus", "cacti")],
}
G3_SENT = {  # (sentence, label) sentiment readouts, partitioned
    "diagnostic": [("I love this wonderful gift", "positive"),
                   ("This awful meal tasted terrible", "negative"),
                   ("What a delightful sunny morning", "positive"),
                   ("The broken machine ruined our day", "negative"),
                   ("She was thrilled with the happy news", "positive")],
    "validation": [("He hated the dreadful weather", "negative"),
                   ("The lovely party was great fun", "positive"),
                   ("A miserable failure disappointed everyone", "negative")],
    "heldout": [("We enjoyed the splendid concert", "positive"),
                ("The nasty storm destroyed the fence", "negative"),
                ("His kind gift made her joyful", "positive"),
                ("That boring lecture was a waste", "negative"),
                ("The charming village delighted visitors", "positive")],
}
VOWELS = set("aeiou")


def gen_g3(split):
    rng = random.Random(SEED["G3"] + SPLIT_SALT[split])
    items = []
    words = list(G3_WORDS[split]); rng.shuffle(words)
    plurals = list(G3_PLURALS[split])
    sents = list(G3_SENT[split])

    def vowel_start():
        w = rng.choice(words)
        return emit(items, "G3", split, "vowel_start",
                    f"Does the word '{w}' start with a vowel or a "
                    f"consonant? Answer with just the word vowel or "
                    f"consonant.",
                    "vowel" if w[0] in VOWELS else "consonant",
                    f"vowelstart({w})")

    def contains_letter():
        if len(words) < 1:
            return False
        w = words[rng.randrange(len(words))]
        letter = rng.choice("abcdefghijklmnopqrstuvwxyz")
        return emit(items, "G3", split, "contains_letter",
                    f"Does the word '{w}' contain the letter "
                    f"'{letter}'? Answer yes or no.",
                    "yes" if letter in w else "no",
                    f"contains({w},{letter})")

    def case_check():
        w = rng.choice(words)
        form = rng.randrange(3)
        shown = [w, w.capitalize(), w.upper()][form]
        return emit(items, "G3", split, "case_check",
                    f"Is the word '{shown}' written in all lowercase "
                    f"letters? Answer yes or no.",
                    "yes" if form == 0 else "no", f"case({shown})")

    def plural_check():
        if not plurals:
            return False
        sg, pl = plurals.pop()
        use_plural = rng.random() < 0.5
        w = pl if use_plural else sg
        gold = "plural" if use_plural else "singular"
        return emit(items, "G3", split, "plural_check",
                    f"Is the word '{w}' singular or plural? "
                    f"Answer with just the word singular or plural.",
                    gold, f"plural({w})")

    def length_compare():
        a, b = rng.sample(words, 2)
        if len(a) == len(b):
            return False
        longer = a if len(a) > len(b) else b
        return emit(items, "G3", split, "length_compare",
                    f"Which word is longer: '{a}' or '{b}'? "
                    f"Answer with just the word.",
                    longer, f"longer({a},{b})")

    def sentiment():
        if not sents:
            return False
        s, lab = sents.pop()
        return emit(items, "G3", split, "sentiment",
                    f"Does this sentence express a positive or a "
                    f"negative feeling: '{s}.' Answer with just the "
                    f"word positive or negative.",
                    lab, f"sentiment({s[:20]})")

    return fill(items, "G3", split,
                [vowel_start, contains_letter, case_check,
                 plural_check, length_compare, sentiment],
                TARGET[split])


# =====================================================================
# G4 -- procedure: multi-step procedures. Date arithmetic in 2026
# (Phase 15's T2 lineage, new year, new frames, disjoint items) plus
# multi-step arithmetic chains. Three frame sets, one per split.
# =====================================================================
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November",
          "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]


def fmt_date(d, split):
    if split == "diagnostic":
        return f"{d.day} {MONTHS[d.month - 1]} 2026"
    if split == "validation":
        return f"{MONTHS[d.month - 1]} {d.day}, 2026"
    return f"{d.day:02d}/{d.month:02d}/2026"


def gen_g4(split):
    rng = random.Random(SEED["G4"] + SPLIT_SALT[split])
    items = []
    f = split  # frame selector

    def rand_date():
        return date(2026, rng.randint(1, 12), rng.randint(1, 28))

    def days_between():
        a = rand_date()
        b = a + timedelta(days=rng.randint(5, 60))
        if b.year != 2026:
            return False
        gap = (b - a).days
        prompts = {
            "diagnostic": f"How many days are there between "
                          f"{fmt_date(a, f)} and {fmt_date(b, f)}? "
                          f"Answer with just the number.",
            "validation": f"Count the days from {fmt_date(a, f)} to "
                          f"{fmt_date(b, f)}. Answer with just the number.",
            "heldout": f"A period begins on {fmt_date(a, f)} and ends "
                       f"on {fmt_date(b, f)}. How many days long is "
                       f"it? Answer with just the number.",
        }
        return emit(items, "G4", split, "days_between", prompts[f],
                    gap, f"{b.timetuple().tm_yday} - {a.timetuple().tm_yday}")

    def weekday_offset():
        a = rand_date()
        n = rng.randint(2, 40)
        wd = a.weekday()  # 0=Monday
        gold = (wd + n) % 7 + 1
        prompts = {
            "diagnostic": f"{fmt_date(a, f)} is a {WEEKDAYS[wd]}. "
                          f"What weekday is it {n} days later? Use "
                          f"Monday=1, Tuesday=2, Wednesday=3, Thursday=4, "
                          f"Friday=5, Saturday=6, Sunday=7. "
                          f"Answer with just the number.",
            "validation": f"Take {fmt_date(a, f)}, which falls on a "
                          f"{WEEKDAYS[wd]}, and move forward {n} days. "
                          f"Give the weekday number (Monday=1 .. "
                          f"Sunday=7). Answer with just the number.",
            "heldout": f"A diary entry dated {fmt_date(a, f)} is "
                       f"marked {WEEKDAYS[wd]}. The entry {n} days "
                       f"after it falls on which weekday number, "
                       f"counting Monday as 1 and Sunday as 7? "
                       f"Answer with just the number.",
        }
        return emit(items, "G4", split, "weekday_offset", prompts[f],
                    gold, f"{wd + 1} + {n} -> {gold}")

    def add_days_month():
        a = rand_date()
        n = rng.randint(5, 90)
        b = a + timedelta(days=n)
        if b.year != 2026:
            return False
        prompts = {
            "diagnostic": f"Starting on {fmt_date(a, f)}, add {n} "
                          f"days. In which month do you land? Use "
                          f"January=1 .. December=12. "
                          f"Answer with just the number.",
            "validation": f"Move {n} days forward from "
                          f"{fmt_date(a, f)}. Give the number of the "
                          f"month you arrive in (January=1 .. "
                          f"December=12). Answer with just the number.",
            "heldout": f"A trip leaves on {fmt_date(a, f)} and "
                       f"returns {n} days later. In which month "
                       f"number (January=1 .. December=12) does it "
                       f"return? Answer with just the number.",
        }
        return emit(items, "G4", split, "add_days_month", prompts[f],
                    b.month, f"month({a.isoformat()} + {n}d)")

    def weeks_days():
        n = rng.randint(11, 120)
        ask_weeks = rng.random() < 0.5
        w, r = divmod(n, 7)
        prompts_w = {
            "diagnostic": f"A span of {n} days is made of whole "
                          f"weeks plus leftover days. How many whole "
                          f"weeks are there? Answer with just the number.",
            "validation": f"Break {n} days into complete weeks and a "
                          f"remainder. Give the number of complete "
                          f"weeks. Answer with just the number.",
            "heldout": f"In {n} days, how many complete seven-day "
                       f"weeks fit? Answer with just the number.",
        }
        prompts_r = {
            "diagnostic": f"A span of {n} days is made of whole "
                          f"weeks plus leftover days. How many "
                          f"leftover days are there? "
                          f"Answer with just the number.",
            "validation": f"Break {n} days into complete weeks and a "
                          f"remainder. Give the remainder, in days. "
                          f"Answer with just the number.",
            "heldout": f"After removing complete seven-day weeks "
                       f"from {n} days, how many days remain? "
                       f"Answer with just the number.",
        }
        if ask_weeks:
            return emit(items, "G4", split, "weeks_days", prompts_w[f],
                        w, f"({n} - {r}) / 7")
        return emit(items, "G4", split, "weeks_days", prompts_r[f],
                    r, f"{n} - {w} * 7")

    def month_span():
        a = rand_date()
        m2 = rng.randint(a.month, 12)
        b = date(2026, m2, rng.randint(1, 28))
        if b <= a:
            return False
        whole = (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)
        prompts = {
            "diagnostic": f"How many whole months pass from "
                          f"{fmt_date(a, f)} to {fmt_date(b, f)}? A "
                          f"whole month means the same day-of-month "
                          f"has been reached again. "
                          f"Answer with just the number.",
            "validation": f"Count complete months between "
                          f"{fmt_date(a, f)} and {fmt_date(b, f)}, "
                          f"where a complete month ends when the "
                          f"starting day-of-month comes round again. "
                          f"Answer with just the number.",
            "heldout": f"A contract starts {fmt_date(a, f)} and "
                       f"ends {fmt_date(b, f)}. How many complete "
                       f"calendar months does it cover, counting a "
                       f"month complete only when the start "
                       f"day-of-month recurs? "
                       f"Answer with just the number.",
        }
        return emit(items, "G4", split, "month_span", prompts[f],
                    whole, f"{b.month} - {a.month} - {1 if b.day < a.day else 0} (span)")

    def arith_chain():
        a, b, c = (rng.randint(11, 99), rng.randint(11, 99),
                   rng.randint(2, 9))
        kind = rng.randrange(2)
        if kind == 0:
            val = (a + b) * c
            prompts = {
                "diagnostic": f"Compute ({a} + {b}) * {c}. "
                              f"Answer with just the number.",
                "validation": f"First add {a} and {b}, then multiply "
                              f"the result by {c}. "
                              f"Answer with just the number.",
                "heldout": f"Take {a}, add {b}, and multiply the "
                           f"total by {c}. "
                           f"Answer with just the number.",
            }
            return emit(items, "G4", split, "arith_chain", prompts[f],
                        val, f"({a} + {b}) * {c}",
                        key=("chain0", min(a, b), max(a, b), c))
        val = a * c - b
        prompts = {
            "diagnostic": f"Compute {a} * {c} - {b}. "
                          f"Answer with just the number.",
            "validation": f"First multiply {a} by {c}, then subtract "
                          f"{b}. Answer with just the number.",
            "heldout": f"Take {a}, multiply it by {c}, and subtract "
                       f"{b}. Answer with just the number.",
        }
        return emit(items, "G4", split, "arith_chain", prompts[f],
                    val, f"{a} * {c} - {b}", key=("chain1", a, b, c))

    return fill(items, "G4", split,
                [days_between, weekday_offset, add_days_month,
                 weeks_days, month_span, arith_chain],
                TARGET[split])


# =====================================================================
# G5 -- factor-knowledge: facts the model must simply know. Authored
# tables; each fact is assigned to exactly ONE split, so splits are
# disjoint at the fact level by construction.
# =====================================================================
CAPITALS = [
    ("France", "Paris"), ("Japan", "Tokyo"), ("Brazil", "Brasilia"),
    ("Canada", "Ottawa"), ("Australia", "Canberra"), ("Egypt", "Cairo"),
    ("India", "New Delhi"), ("Spain", "Madrid"), ("Italy", "Rome"),
    ("Germany", "Berlin"), ("Norway", "Oslo"), ("Sweden", "Stockholm"),
    ("Finland", "Helsinki"), ("Denmark", "Copenhagen"),
    ("Poland", "Warsaw"), ("Greece", "Athens"), ("Turkey", "Ankara"),
    ("Kenya", "Nairobi"), ("Chile", "Santiago"), ("Peru", "Lima"),
    ("Argentina", "Buenos Aires"), ("Mexico", "Mexico City"),
    ("Thailand", "Bangkok"), ("Vietnam", "Hanoi"),
    ("Indonesia", "Jakarta"), ("Malaysia", "Kuala Lumpur"),
    ("Philippines", "Manila"), ("Pakistan", "Islamabad"),
    ("Iran", "Tehran"), ("Iraq", "Baghdad"), ("Morocco", "Rabat"),
    ("Ethiopia", "Addis Ababa"), ("Nigeria", "Abuja"),
    ("Ukraine", "Kyiv"), ("Romania", "Bucharest"),
    ("Hungary", "Budapest"), ("Austria", "Vienna"),
    ("Switzerland", "Bern"), ("Netherlands", "Amsterdam"),
    ("Belgium", "Brussels"), ("Portugal", "Lisbon"),
    ("Ireland", "Dublin"), ("Iceland", "Reykjavik"),
    ("Mongolia", "Ulaanbaatar"), ("Nepal", "Kathmandu"),
    ("Sri Lanka", "Colombo"), ("Myanmar", "Naypyidaw"),
    ("Cambodia", "Phnom Penh"), ("Laos", "Vientiane"),
    ("Cuba", "Havana"), ("Jamaica", "Kingston"),
    ("Panama", "Panama City"), ("Ecuador", "Quito"),
    ("Bolivia", "Sucre"), ("Paraguay", "Asuncion"),
    ("Uruguay", "Montevideo"), ("Venezuela", "Caracas"),
    ("Colombia", "Bogota"), ("Algeria", "Algiers"),
    ("Libya", "Tripoli"), ("Sudan", "Khartoum"),
    ("Angola", "Luanda"), ("Zambia", "Lusaka"),
    ("Zimbabwe", "Harare"), ("Mozambique", "Maputo"),
    ("Madagascar", "Antananarivo"), ("Tanzania", "Dodoma"),
    ("Uganda", "Kampala"), ("Ghana", "Accra"), ("Senegal", "Dakar"),
    ("South Korea", "Seoul"), ("China", "Beijing"), ("Russia", "Moscow"),
    ("Kazakhstan", "Astana"), ("Uzbekistan", "Tashkent"),
    ("Kyrgyzstan", "Bishkek"), ("Tajikistan", "Dushanbe"),
    ("Turkmenistan", "Ashgabat"), ("Afghanistan", "Kabul"),
    ("Bangladesh", "Dhaka"), ("Bhutan", "Thimphu"),
    ("Maldives", "Male"), ("Brunei", "Bandar Seri Begawan"),
    ("Timor-Leste", "Dili"), ("Fiji", "Suva"),
    ("Papua New Guinea", "Port Moresby"),
    ("New Zealand", "Wellington"), ("Samoa", "Apia"),
]
ELEMENTS_SYMBOL = [  # name -> symbol
    ("iron", "Fe"), ("gold", "Au"), ("silver", "Ag"), ("copper", "Cu"),
    ("zinc", "Zn"), ("tin", "Sn"), ("lead", "Pb"), ("oxygen", "O"),
    ("hydrogen", "H"), ("carbon", "C"), ("nitrogen", "N"),
    ("sodium", "Na"), ("potassium", "K"), ("calcium", "Ca"),
    ("aluminium", "Al"), ("silicon", "Si"), ("phosphorus", "P"),
    ("sulfur", "S"), ("chlorine", "Cl"), ("argon", "Ar"),
    ("helium", "He"), ("lithium", "Li"), ("boron", "B"),
    ("fluorine", "F"), ("neon", "Ne"), ("magnesium", "Mg"),
    ("titanium", "Ti"), ("chromium", "Cr"), ("manganese", "Mn"),
    ("cobalt", "Co"), ("nickel", "Ni"), ("platinum", "Pt"),
    ("mercury", "Hg"), ("uranium", "U"), ("iodine", "I"),
    ("bromine", "Br"), ("xenon", "Xe"), ("radon", "Rn"),
    ("tungsten", "W"), ("barium", "Ba"),
]
ELEMENTS_NAME = [  # symbol -> name (disjoint elements from above)
    ("NaCl-note", None),  # placeholder removed below
]
ELEMENTS_NAME = [
    ("Sc", "scandium"), ("V", "vanadium"), ("Ga", "gallium"),
    ("Ge", "germanium"), ("As", "arsenic"), ("Se", "selenium"),
    ("Rb", "rubidium"), ("Sr", "strontium"), ("Y", "yttrium"),
    ("Zr", "zirconium"), ("Nb", "niobium"), ("Mo", "molybdenum"),
    ("Cd", "cadmium"), ("In", "indium"), ("Sb", "antimony"),
    ("Te", "tellurium"), ("Cs", "caesium"), ("La", "lanthanum"),
    ("Ce", "cerium"), ("Nd", "neodymium"), ("Sm", "samarium"),
    ("Eu", "europium"), ("Gd", "gadolinium"), ("Tb", "terbium"),
]
SOLAR = [
    ("Which planet is closest to the Sun?", "Mercury"),
    ("Which planet is known as the Red Planet?", "Mars"),
    ("Which is the largest planet in our solar system?", "Jupiter"),
    ("Which planet has the most prominent rings?", "Saturn"),
    ("Which planet is farthest from the Sun?", "Neptune"),
    ("Which planet is second from the Sun?", "Venus"),
    ("How many planets are in our solar system?", "8"),
    ("What is the name of Earth's only natural satellite?", "Moon"),
    ("Which star is at the centre of our solar system?", "Sun"),
    ("Which planet is known as the Morning Star?", "Venus"),
    ("Which planet rotates on its side, tilted about 98 degrees?", "Uranus"),
    ("Which dwarf planet beyond Neptune was once the ninth planet?", "Pluto"),
    ("What is the largest moon of Saturn?", "Titan"),
    ("What is the largest moon of Jupiter?", "Ganymede"),
    ("Which planet has the Great Red Spot?", "Jupiter"),
    ("Which planet has a day longer than its year?", "Venus"),
    ("What galaxy is our solar system part of?", "Milky Way"),
    ("Which planet is home to Olympus Mons, the tallest volcano?", "Mars"),
    ("How many moons does Mars have?", "2"),
    ("Which planet's rings are made mostly of ice particles?", "Saturn"),
    ("What is the hottest planet in our solar system?", "Venus"),
    ("Which planet was discovered by telescope first, in 1781?", "Uranus"),
    ("What is the name of the force that keeps planets in orbit?", "gravity"),
    ("How long does Earth take to orbit the Sun, in days?", "365"),
    ("Which planet has the shortest day, about 10 hours?", "Jupiter"),
    ("What is the Sun mainly made of: hydrogen or iron?", "hydrogen"),
    ("Which moon of Jupiter is thought to hide a liquid ocean under ice?", "Europa"),
    ("What is the asteroid belt located between: Mars and which planet?", "Jupiter"),
]
UNIT_FACTS = [
    ("How many seconds are in one minute?", "60"),
    ("How many minutes are in one hour?", "60"),
    ("How many hours are in one day?", "24"),
    ("How many days are in one week?", "7"),
    ("How many months are in one year?", "12"),
    ("How many centimetres are in one metre?", "100"),
    ("How many metres are in one kilometre?", "1000"),
    ("How many millimetres are in one centimetre?", "10"),
    ("How many grams are in one kilogram?", "1000"),
    ("How many kilograms are in one tonne?", "1000"),
    ("How many millilitres are in one litre?", "1000"),
    ("How many items are in one dozen?", "12"),
    ("How many items are in one gross?", "144"),
    ("How many inches are in one foot?", "12"),
    ("How many feet are in one yard?", "3"),
    ("How many feet are in one mile?", "5280"),
    ("How many sides does a hexagon have?", "6"),
    ("How many sides does an octagon have?", "8"),
    ("How many degrees are in a right angle?", "90"),
    ("How many degrees are in a full circle?", "360"),
    ("How many minutes are in one day?", "1440"),
    ("How many weeks are in one year (whole weeks)?", "52"),
    ("How many millimetres are in one metre?", "1000"),
    ("How many litres are in one cubic metre?", "1000"),
    ("How many hours are in one week?", "168"),
    ("How many seconds are in one hour?", "3600"),
    ("How many days are in a leap year?", "366"),
    ("How many cents are in one US dollar?", "100"),
    ("How many ounces are in one pound?", "16"),
    ("How many pints are in one quart?", "2"),
]
ANIMAL_MISC = [
    ("What is the largest land animal?", "African elephant"),
    ("What is the fastest land animal?", "cheetah"),
    ("What is the largest mammal in the world?", "blue whale"),
    ("How many legs does a spider have?", "8"),
    ("How many legs does an insect have?", "6"),
    ("What do caterpillars turn into?", "butterflies"),
    ("What is a baby frog called?", "tadpole"),
    ("What is a baby horse called?", "foal"),
    ("What is a baby dog called?", "puppy"),
    ("What is a baby cat called?", "kitten"),
    ("What is a baby sheep called?", "lamb"),
    ("What is a baby cow called?", "calf"),
    ("Which bird cannot fly but swims in the Antarctic?", "penguin"),
    ("Which animal is known as man's best friend?", "dog"),
    ("What colour do you get by mixing blue and yellow paint?", "green"),
    ("What colour do you get by mixing red and white paint?", "pink"),
    ("What colour do you get by mixing red and blue paint?", "purple"),
    ("At what temperature Celsius does water freeze?", "0"),
    ("At what temperature Celsius does water boil at sea level?", "100"),
    ("What gas do plants absorb from the air?", "carbon dioxide"),
    ("What gas do humans need to breathe to live?", "oxygen"),
    ("What is H2O commonly known as?", "water"),
    ("How many continents are there on Earth?", "7"),
    ("What is the largest continent?", "Asia"),
    ("What is the smallest continent?", "Australia"),
    ("What is the largest ocean on Earth?", "Pacific Ocean"),
    ("What is the longest river in the world?", "Nile"),
    ("What is the largest hot desert in the world?", "Sahara"),
    ("What is the tallest mountain above sea level?", "Mount Everest"),
    ("What is the capital city of the United Kingdom?", "London"),
    ("In which country is the Great Wall?", "China"),
    ("In which country are the pyramids of Giza?", "Egypt"),
    ("What is the main language of Brazil?", "Portuguese"),
    ("What is the main language of Mexico?", "Spanish"),
    ("Who wrote the play Romeo and Juliet?", "William Shakespeare"),
    ("Who painted the Mona Lisa?", "Leonardo da Vinci"),
]
HISTORY_MISC = [
    ("In which year did humans first land on the Moon?", "1969"),
    ("In which year did World War II end?", "1945"),
    ("In which year did World War I begin?", "1914"),
    ("Who was the first President of the United States?", "George Washington"),
    ("Which ancient civilisation built the pyramids of Giza?", "Egyptians"),
    ("What did Alexander Graham Bell invent?", "telephone"),
    ("Who invented the first practical light bulb?", "Thomas Edison"),
    ("What is the currency of Japan?", "yen"),
    ("What is the currency of the United Kingdom?", "pound"),
    ("What is the currency of Switzerland?", "Swiss franc"),
    ("What is the currency of India?", "rupee"),
    ("What is the currency of China?", "yuan"),
    ("How many players of one football (soccer) team are on the field at once?", "11"),
    ("How many rings are on the Olympic flag?", "5"),
    ("In tennis, what is a score of zero called?", "love"),
    ("How many squares are on a standard chess board?", "64"),
    ("How many pieces does each player start with in chess?", "16"),
    ("How many hydrogen atoms are in one molecule of water?", "2"),
    ("How many strings does a standard guitar have?", "6"),
    ("How many keys does a standard piano have?", "88"),
    ("How many symphonies did Beethoven compose?", "9"),
    ("What instrument measures temperature?", "thermometer"),
    ("What instrument measures earthquakes?", "seismograph"),
    ("In which year did the Berlin Wall fall?", "1989"),
]


def g5_pool():
    pool = []  # (category, prompt, answer)
    for country, cap in CAPITALS:
        pool.append(("capital",
                     f"What is the capital of {country}? "
                     f"Answer with just the name.", cap))
    for name, sym in ELEMENTS_SYMBOL:
        pool.append(("element_symbol",
                     f"What is the chemical symbol for {name}? "
                     f"Answer with just the symbol.", sym))
    for sym, name in ELEMENTS_NAME:
        pool.append(("element_name",
                     f"Which element has the chemical symbol {sym}? "
                     f"Answer with just the name.", name))
    for q, a in SOLAR:
        pool.append(("solar", q + " Answer with just the answer.", a))
    for q, a in UNIT_FACTS:
        pool.append(("unit_fact", q + " Answer with just the number.", a))
    for q, a in ANIMAL_MISC:
        pool.append(("animal_misc", q + " Answer with just the answer.", a))
    for q, a in HISTORY_MISC:
        pool.append(("history_misc", q + " Answer with just the answer.", a))
    return pool


def gen_g5(split):
    pool = g5_pool()
    rng = random.Random(SEED["G5"])
    rng.shuffle(pool)
    targets = {"diagnostic": 100, "validation": 60, "heldout": 100}
    # contiguous partition of the shuffled pool: disjoint by construction
    starts = {"diagnostic": 0, "validation": 100, "heldout": 160}
    mine = pool[starts[split]:starts[split] + targets[split]]
    items = []
    for cat, prompt, ans in mine:
        emit(items, "G5", split, cat, prompt, ans, f"fact({prompt})")
    return items


# =====================================================================
# G6 -- unseparated relation: paired decision contexts in the E8
# geometry. Two bookings; the gold flips ONLY on the contention
# relation (same exclusive seat + overlapping time + different lane
# -> HOLD; every other relation -> ALLOW). Each scenario emits a
# minimal pair: the contention variant and one non-contention variant
# differing in exactly one relation component.
# =====================================================================
G6_BOXES = ["thor", "orin", "proart"]
G6_SEATS = ["zcode", "mcode", "gpu", "claude"]
G6_LANES = {
    "diagnostic": ["chrono-tensor", "quilt-engine", "signal-chain",
                   "foundry", "jev-rack", "radio-room"],
    "validation": ["lan-mesh", "download-governor", "image-studio",
                   "gpu-queue"],
    "heldout": ["telltape", "confluence", "patchbay", "anchor-desk",
                "wsp-bench", "seat-audit"],
}
G6_TASKS = {
    "diagnostic": ["audit the booking ledger", "rebuild the index",
                   "run the conformance sweep", "profile the queue"],
    "validation": ["verify the tunnel map", "sweep the registry",
                   "check the cache state"],
    "heldout": ["replay the decision log", "audit the seat board",
                "sweep the witness file", "profile the scheduler"],
}
POLICY = ("policy facts: exclusive seats are single-driver; first "
          "booking wins ties; a booking past its check-by does not "
          "contend; same-lane overlaps are renewals")


def _hhmm(mins):
    return f"{mins // 60:02d}:{mins % 60:02d}"


def gen_g6(split):
    rng = random.Random(SEED["G6"] + SPLIT_SALT[split])
    items = []
    lanes = G6_LANES[split]
    tasks = G6_TASKS[split]
    pair_no = 0

    def scenario():
        nonlocal pair_no
        box = rng.choice(G6_BOXES)
        seat = rng.choice(G6_SEATS)
        other_seat = rng.choice([s for s in G6_SEATS if s != seat])
        other_box = rng.choice([b for b in G6_BOXES if b != box])
        lane_a, lane_b = rng.sample(lanes, 2)
        task = rng.choice(tasks)
        start = rng.randint(8 * 60, 15 * 60)
        dur = rng.choice([60, 90, 120])
        end = start + dur
        pair_no += 1
        pid = f"pair-{pair_no:03d}"

        def render(lane_new, box_new, seat_new, s_new, e_new,
                   checkby_new, expired=False):
            cb = checkby_new
            ex_start, ex_dur, ex_cb = start, dur, end + 60
            ex_note = ""
            if expired:
                # existing planned window overlaps the new request,
                # but its check-by passed 15m before the new start
                # with no heartbeat: it does not contend.
                ex_start, ex_dur = s_new - 30, 120
                ex_cb = s_new - 15
                ex_note = " (check-by passed, no heartbeat)"
            ctx_existing = (
                f"existing booking: producer: {lane_a}; resource: "
                f"{box} seat {seat}; start: 2026-11-05 "
                f"{_hhmm(ex_start)} UTC; planned duration: {ex_dur}m; "
                f"check-by: 2026-11-05 {_hhmm(ex_cb)} UTC{ex_note}")
            ctx_new = (
                f"new request: producer: {lane_new}; effect: write "
                f"booking/{box_new}/{seat_new}; resource: {box_new} "
                f"seat {seat_new}; start: 2026-11-05 "
                f"{_hhmm(s_new)} UTC; planned duration: "
                f"{e_new - s_new}m; check-by: 2026-11-05 "
                f"{_hhmm(cb)} UTC; task: {task}; {POLICY}")
            return (f"Decide ALLOW or HOLD for the new request.\n"
                    f"{ctx_existing}\n{ctx_new}\n"
                    f"Answer with just ALLOW or HOLD.")

        # contention variant: same box+seat, different lane, overlap
        s2 = start + rng.choice([15, 30, 45])
        ok1 = emit(items, "G6", split, "contention_same_seat",
                   render(lane_b, box, seat, s2, s2 + dur, s2 + dur + 60),
                   "HOLD", f"g6({split}-{pid},contention)", pair_id=pid)
        # non-contention variant: exactly one component changed
        variant = rng.choice(["different_seat", "different_box",
                              "time_disjoint", "same_lane_renewal",
                              "expired_booking"])
        if variant == "different_seat":
            p, gold = render(lane_b, box, other_seat, s2, s2 + dur,
                             s2 + dur + 60), "ALLOW"
        elif variant == "different_box":
            p, gold = render(lane_b, other_box, seat, s2, s2 + dur,
                             s2 + dur + 60), "ALLOW"
        elif variant == "time_disjoint":
            p, gold = render(lane_b, box, seat, end + 30,
                             end + 30 + dur, end + 30 + dur + 60), "ALLOW"
        elif variant == "same_lane_renewal":
            p, gold = render(lane_a, box, seat, s2, s2 + dur,
                             s2 + dur + 60), "ALLOW"
        else:
            p, gold = render(lane_b, box, seat, s2, s2 + dur,
                             s2 + dur + 60, expired=True), "ALLOW"
        ok2 = emit(items, "G6", split, variant, p, gold,
                   f"g6({split}-{pid},{variant})", pair_id=pid)
        return ok1 and ok2

    return fill(items, "G6", split, [scenario], TARGET[split])


GENERATORS = {"G1": gen_g1, "G2": gen_g2, "G3": gen_g3,
              "G4": gen_g4, "G5": gen_g5, "G6": gen_g6}


def main():
    manifest = {}
    for grade, gen in GENERATORS.items():
        for split in SPLITS:
            items = gen(split)
            path = HERE / f"{grade.lower()}_{split}.jsonl"
            with open(path, "w") as fh:
                for it in items:
                    fh.write(json.dumps(it, ensure_ascii=False) + "\n")
            from collections import Counter
            manifest[f"{grade}/{split}"] = {
                "n": len(items),
                "categories": dict(Counter(i["category"] for i in items)),
                "answers": dict(Counter(i["answer"] for i in items)
                                ) if grade == "G6" else None,
            }
            print(f"{grade} {split}: {len(items)} items -> {path.name}")
    with open(HERE / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=1)
    print("manifest.json written")


if __name__ == "__main__":
    main()
