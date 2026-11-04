#!/usr/bin/env python3
"""Seeded round-battery generator for Jacquard Phase 15, slice 43 (E6).

The E6 teacher-student patch loop needs a FRESH diagnostic battery
for every loop round, so the loop's patcher never tunes twice on
the same items. This generator builds those round batteries. It
does NOT patch any model.

Writes (paths relative to this script):
  batteries/rounds/round1_diag.jsonl   60 arithmetic items (set A)
  batteries/rounds/round2_diag.jsonl   60 arithmetic items (set A)
  batteries/rounds/round3_diag.jsonl   60 arithmetic items (set A)
  batteries/rounds/round4_diag.jsonl   60 arithmetic items (set A)
  batteries/rounds/round5_diag.jsonl   60 arithmetic items (set A)
  batteries/rounds/round6_diag.jsonl   60 arithmetic items (set A)

Discipline is exactly the slice-41 discipline of gen_batteries.py:
the same 8 arithmetic categories, the same set-A template code and
lexical pool A (imported from gen_batteries.py, not re-implemented),
the same prompt suffix "Answer with just the number.", and the
same item schema {"id", "split", "category", "prompt", "answer",
"derivation"}.

Category balance: 60 items over 8 categories is 7-8 per category.
The four categories that receive 8 rotate by round (rounds 1, 3, 5
give 8 to the first four categories in CATEGORIES order; rounds
2, 4, 6 give 8 to the last four), so every category totals exactly
45 items across the six rounds.

Seeds continue the sequence used by gen_batteries.py and
gen_batteries2.py without collision:
  slice 41 (gen_batteries.py):  diagnostic 15041, validation 15042,
                                heldout 15043, forget_instr 15044,
                                forget_fact 15045
  slice 42 (gen_batteries2.py): t2_diag 15046, t2_held 15047,
                                t3_diag 15048, t3_held 15049
  slice 43 (this file):         round1 15050, round2 15051,
                                round3 15052, round4 15053,
                                round5 15054, round6 15055

Uniqueness (hard constraint): every prompt string AND every
derivation string is unique across ALL arithmetic batteries in
the study's arithmetic family -- the three slice-41 splits
(diagnostic, validation, heldout) AND all six round files. The
t2/t3 files are different task families and are not part of this
arithmetic dedup scope, per the slice-43 brief. The seen-sets are
seeded from the slice-41 files on disk before any round item is
generated (the seed_seen / resample-on-collision pattern of
gen_batteries2.py, which itself follows the seen-set machinery of
gen_batteries.py's build_arith_split), and each accepted round
item is added to the sets, so rounds are also mutually disjoint.

Python stdlib only (plus the sibling gen_batteries.py import).
Fully deterministic: fixed seeds, no wall clock, no environment
dependence. Run:  python3 gen_rounds.py
"""
import json
import random
from pathlib import Path

from gen_batteries import CATEGORIES, GEN_A

HERE = Path(__file__).resolve().parent

SEEDS = {1: 15050, 2: 15051, 3: 15052, 4: 15053, 5: 15054, 6: 15055}
ROUNDS = [1, 2, 3, 4, 5, 6]
ITEMS_PER_ROUND = 60

# Existing arithmetic files whose prompts/derivations seed the
# seen-sets. Heldout lives in private/ (the enforcement boundary);
# it is read here only as a dedup source, never copied or emitted.
EXISTING_ARITH_FILES = [
    HERE / "batteries" / "diagnostic.jsonl",
    HERE / "batteries" / "validation.jsonl",
    HERE / "private" / "heldout.jsonl",
]


def seed_seen():
    """Seed the seen-sets from every existing arithmetic file so
    no prompt or derivation from slice 41 can recur in a round."""
    seen_prompts, seen_derivs = set(), set()
    for path in EXISTING_ARITH_FILES:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                it = json.loads(line)
                if it.get("prompt"):
                    seen_prompts.add(it["prompt"])
                if it.get("derivation"):
                    seen_derivs.add(it["derivation"])
    return seen_prompts, seen_derivs


def counts_for_round(round_no):
    """Per-category targets for one round: 7 each, plus 1 extra
    for four categories (8), rotating by round. Rounds 1/3/5 give
    the extra to CATEGORIES[:4]; rounds 2/4/6 to CATEGORIES[4:].
    Total is 60; across six rounds each category totals 45."""
    counts = {cat: 7 for cat in CATEGORIES}
    start = 0 if round_no % 2 == 1 else 4
    for cat in CATEGORIES[start:start + 4]:
        counts[cat] = 8
    assert sum(counts.values()) == ITEMS_PER_ROUND
    return counts


def build_round(round_no, seed, seen_prompts, seen_derivs):
    """One round battery, using the slice-41 set-A generators
    (GEN_A) and per-round seed. Resamples on any prompt or
    derivation collision with the global seen-sets, exactly as
    build_arith_split in gen_batteries.py does."""
    split = f"round{round_no}_diag"
    prefix = f"r{round_no}diag"
    counts = counts_for_round(round_no)
    rng = random.Random(seed)
    items = []
    n = 0
    for cat in CATEGORIES:
        made = 0
        attempts = 0
        while made < counts[cat]:
            attempts += 1
            if attempts > 10000:
                raise RuntimeError(f"cannot fill {split}/{cat}")
            prompt, answer, deriv = GEN_A[cat](rng)
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
    seeded_prompts = len(seen_prompts)
    seeded_derivs = len(seen_derivs)
    out_dir = HERE / "batteries" / "rounds"
    for round_no in ROUNDS:
        items = build_round(round_no, SEEDS[round_no],
                            seen_prompts, seen_derivs)
        assert len(items) == ITEMS_PER_ROUND
        write_jsonl(out_dir / f"round{round_no}_diag.jsonl", items)
        print(f"round{round_no}_diag: {len(items)} items "
              f"(seed {SEEDS[round_no]})")
    print(f"seen-sets seeded from slice-41 arithmetic files: "
          f"{seeded_prompts} prompts, {seeded_derivs} derivations; "
          f"after rounds: {len(seen_prompts)} prompts, "
          f"{len(seen_derivs)} derivations")


if __name__ == "__main__":
    main()
