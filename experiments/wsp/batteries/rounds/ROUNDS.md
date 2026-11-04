# Phase 15 Round Batteries — Slice 43 (E6)

Fresh diagnostic batteries for the E6 teacher-student patch loop:
one new battery per loop round, so the loop's patcher never tunes
twice on the same items. Built by the battery seat with
`gen_rounds.py` (in `experiments/wsp/`); this seat does not patch
any model. Verification is by `verify_rounds.py` (independent of
the generator); its saved output is `VERIFY-ROUNDS.txt` in this
directory.

## Files

| file | items | split field | seed |
|---|---|---|---|
| `round1_diag.jsonl` | 60 arithmetic | `round1_diag` | 15050 |
| `round2_diag.jsonl` | 60 arithmetic | `round2_diag` | 15051 |
| `round3_diag.jsonl` | 60 arithmetic | `round3_diag` | 15052 |
| `round4_diag.jsonl` | 60 arithmetic | `round4_diag` | 15053 |
| `round5_diag.jsonl` | 60 arithmetic | `round5_diag` | 15054 |
| `round6_diag.jsonl` | 60 arithmetic | `round6_diag` | 15055 |
| `VERIFY-ROUNDS.txt` | — | saved verifier output | — |

Item schema is the slice-41 schema: `{"id", "split", "category",
"prompt", "answer", "derivation"}`, ids `r<round>diag-001` …
`r<round>diag-060`. Every prompt ends with
"Answer with just the number."

## Seeds

Seeds continue the existing sequence without collision:
slice 41 (`gen_batteries.py`) used 15041–15045 (diagnostic,
validation, heldout, forget_instr, forget_fact) and slice 42
(`gen_batteries2.py`) used 15046–15049 (t2_diag, t2_held, t3_diag,
t3_held). The round seeds are therefore 15050–15055, one per
round, in round order, each used as `random.Random(seed)` exactly
as in the earlier generators.

## Generation discipline

Same as slice 41: the eight arithmetic categories (`addsub_chain`,
`mul_2x1`, `mul_2x2`, `div_exact`, `pct_of`, `word_2step`,
`unit_price`, `compare`), template set A and lexical pool A only —
the generator imports `GEN_A` and `CATEGORIES` from
`gen_batteries.py` rather than re-implementing them, so the round
items come from the identical template code as diagnostic and
validation.

## Counts and category balance

60 items per round, 360 in total. 60 over 8 categories is 7–8 per
category per round. The four categories receiving 8 rotate by
round: rounds 1, 3, 5 give 8 to `addsub_chain`, `mul_2x1`,
`mul_2x2`, `div_exact` and 7 to the other four; rounds 2, 4, 6
give 8 to `pct_of`, `word_2step`, `unit_price`, `compare` and 7
to the other four. Across all six rounds every category therefore
totals exactly 45 items. The verifier's per-round category counts
are recorded in `VERIFY-ROUNDS.txt`.

## Disjointness guarantees

Enforced in the generator by construction, and re-checked
independently by the verifier:

- Every prompt string is unique within each round file, across
  all six round files, and against `batteries/diagnostic.jsonl`,
  `batteries/validation.jsonl` and `private/heldout.jsonl`.
- Every derivation string is unique under the same scope. A
  repeated worked example under different wording is therefore
  excluded, not just a repeated prompt.
- Mechanism: before generating, `gen_rounds.py` seeds its
  seen-sets from the three slice-41 arithmetic files on disk
  (480 prompts and 480 derivations at build time, following the
  `seed_seen` pattern of `gen_batteries2.py`); every candidate
  item that collides on either key is resampled, and every
  accepted item is added to the sets, so later rounds are also
  disjoint from earlier rounds. After all six rounds the sets
  held 840 prompts and 840 derivations (480 + 360).
- Scope note: the t2/t3 files are different task families
  (date/interval and unit-conversion) and are not part of this
  arithmetic dedup scope, per the slice-43 brief.

## Verification

`verify_rounds.py` imports neither generator. It checks counts
(60 × 6), category balance (7–8 per category per round),
derivation recompute with a restricted AST evaluator, prompt and
derivation uniqueness under the scope above, word_2step
non-negativity, and an independent prompt-parse recompute written
in the verifier itself (fresh regex parser; the derivation string
is never used). Final result: PASS, with prompt-parse coverage
360/360 round items (100.0%, against a ≥60% requirement) and every
parsed answer matching the stored answer. Full output:
`VERIFY-ROUNDS.txt` in this directory.

## Determinism

Generation is fully deterministic (fixed seeds, Python stdlib
`random`, no wall clock). Regenerating with
`python3 gen_rounds.py` reproduced all six files byte-identically;
md5sums before and after regeneration matched:

```
9cf714f51b49beab2cd99b5e16bb4862  round1_diag.jsonl
8bdad845791f13d0d2a5f21bc39b0cd9  round2_diag.jsonl
7752c47d0b7ab7793b3ea9c8d5527c27  round3_diag.jsonl
440ea5e72f4815f62a727d3048783c81  round4_diag.jsonl
fcb3c2d68e0b82cf3bc9f07355fec5dd  round5_diag.jsonl
c021372500fb2cfb685922d7e4fa16c1  round6_diag.jsonl
```

## Reproduce

```
cd experiments/wsp
python3 gen_rounds.py       # writes batteries/rounds/round*_diag.jsonl
python3 verify_rounds.py    # writes batteries/rounds/VERIFY-ROUNDS.txt
```
