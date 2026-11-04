# Phase 15 Batteries, Slice 42 — Design Document (E5 families)

Instruments for experiment E5 (successive-task forgetting) in the
weight-space programming study (PLAN.md, slice 42). Built by the
battery seat as an extension of the slice-41 instrument
(BATTERIES.md); the discipline of that instrument is matched
exactly: seeded deterministic generation (Python stdlib `random`),
a patcher-visible diagnostic set written with template set A and a
genuinely separate template set B (separate code, disjoint lexical
pools) for heldout, prompt AND derivation strings deduplicated
across **all** splits old and new, every prompt ending in
"Answer with just the number.", every gold a JSON number (integer
or exact 2-decimal), and code-only scoring. This generator does
not patch any model.

## Files

| file | items | visibility |
|---|---|---|
| `batteries/t2_diagnostic.jsonl` | 60 date/interval | patcher-visible |
| `private/t2_heldout.jsonl` | 120 date/interval | coordinator-only |
| `batteries/t3_diagnostic.jsonl` | 60 unit conversion | patcher-visible |
| `private/t3_heldout.jsonl` | 120 unit conversion | coordinator-only |
| `batteries/setA2_markers.json` | 31 markers | generated; verifier input |
| `batteries/VERIFY2.txt` | — | saved output of the verifier |

Item shape is unchanged: `{"id", "split", "category", "prompt",
"answer", "derivation"}`. Split fields are `t2_diagnostic`,
`t2_heldout`, `t3_diagnostic`, `t3_heldout`; ids are `t2diag-`,
`t2held-`, `t3diag-`, `t3held-` plus a running number. The
`private/` boundary is the same as slice 41: heldout material
lives only there.

## Family T2 — date / interval arithmetic

All items are set in **2025, a non-leap year** (no leap-day
ambiguity), and the year is stated in every prompt. Every gold is
computed with Python's `datetime` in the generator; no calendar
math is hand-rolled.

Five categories, exactly equal proportions (diagnostic 12 each,
heldout 24 each):

- `days_between` — days between two stated dates in 2025
  (gaps of 5–60 days). Derivation is day-of-year subtraction,
  e.g. `243 - 234`.
- `weekday_offset` — the prompt states a date's true weekday and
  asks for the weekday a stated number of days (2–40) later.
  The answer is a NUMBER under the mapping **Monday=1, Tuesday=2,
  Wednesday=3, Thursday=4, Friday=5, Saturday=6, Sunday=7**, and
  that mapping is stated in full in every weekday_offset prompt,
  both splits. Derivation folds the week wrap into plain
  arithmetic, e.g. `7 + 19 - 21` for Sunday + 19 days.
- `add_days_count` — two variants, alternated deterministically:
  (a) a start date plus N days (5–90) lands in which month —
  answer the month NUMBER 1–12, with the January=1 … December=12
  mapping stated in the prompt; derivation `max(m_start, m_end)`
  (adding days never moves to an earlier month within the year);
  (b) how many days from a date to the end of its month, not
  counting the date itself — derivation `days_in_month - day`.
- `weeks_days` — a span of 11–120 days expressed as whole weeks
  plus remaining days; the prompt asks for exactly one component,
  stated clearly ("How many whole weeks are there?" /
  "How many leftover days are there?" in set A2; "Give the number
  of complete weeks." / "Give the remainder, in days." in set B2).
  Derivations: `(n - r) / 7` for weeks, `n - w * 7` for the
  remainder.
- `month_span` — whole months between two dates in the same
  year. **Definition (resolved ambiguity):** a whole month is a
  complete calendar month — the month difference, minus one if
  the end date's day-of-month has not yet reached the start
  date's day-of-month (the "birthday rule"). The prompts state
  this definition in words ("A whole month means the same
  day-of-month has been reached again" / "a complete month ends
  when the starting day-of-month comes round again"), and the
  verifier's prompt parser applies the identical rule.
  Derivations: `m2 - m1` or `m2 - m1 - 1`.

Derivations stay inside the slice-41 restricted expression
language (+ − × ÷, parentheses, numeric literals, max/min) so the
same AST evaluator recomputes every one of them; the calendar
content is carried by the operands (day-of-year numbers, month
numbers, days-in-month), which the generator derives from
`datetime`/`calendar`.

Surface forms: set A2 writes dates as `10 March 2025`, set B2 as
`March 10, 2025`.

## Family T3 — unit conversion (exact only)

Six categories, exactly equal proportions (diagnostic 10 each,
heldout 20 each). Every conversion factor is an exact integer;
results are integers, except that divisions by 100 or 1000
sometimes carry a quarter offset (e.g. `11750 / 1000` = 11.75),
giving exact 2-decimal answers. Both directions of every pair are
represented. Derivations are single operations, `v * ratio`
downhill (to the smaller unit) or `v / divisor` uphill, where the
uphill value is constructed from a drawn integer result so the
division is exact.

- `time_conv` — hours↔minutes (60), minutes↔seconds (60),
  days↔hours (24).
- `metric_length` — kilometres↔metres (1000), metres↔centimetres
  (100), centimetres↔millimetres (10), metres↔millimetres (1000).
- `imperial_length` — miles↔feet (5280), yards↔feet (3),
  feet↔inches (12).
- `dozen_gross` — dozen = 12 items, gross = 144 items, and
  gross↔dozen (12).
- `metric_mass` — tonnes↔kilograms (1000), kilograms↔grams
  (1000), tonnes↔grams (1000000).
- `metric_volume` — litres↔millilitres (1000), cubic
  metres↔litres (1000), cubic metres↔millilitres (1000000).

## Template set A2 vs set B2

Diagnostic files use template set A2 with lexical pool A2 (names
Harper, Oscar, Clara, Hugo, Rosa, Ben, Ivy, Samuel; objects
screws, candles, postcards, muffins, napkins, pebbles, planks,
bottles); heldout files use template set B2 with pool B2 (names
Yuki, Omar, Lena, Ravi, Astrid, Diego, Mei, Karl). Both pools are
disjoint from each other and from both slice-41 pools. Set B2 is
separate generator code (`b2_*` functions and a separate t3 frame
set), not parameter tweaks of set A2: different sentence frames
("Count the days between … The count is what?", "… equals how
many …?", "Stated in …, the amount is what?") and the second date
surface form above.

Two strings are shared by both sets **by specification**, not by
leakage: the weekday mapping (Monday=1 … Sunday=7) and the month
mapping (January=1 … December=12) must be stated in the prompts
that use them, in both splits. Neither mapping string is a
marker.

Marker hygiene: the generator emits `batteries/setA2_markers.json`
with all pool-A2 strings (8 names + 8 objects) plus 15 set-A2
template frame fragments ("Convert", "how many days pass from",
"What weekday is it", "falls in which month", …) — 31 markers.
The verifier asserts that no marker from **either**
`setA_markers.json` (slice 41, 47 markers) **or**
`setA2_markers.json` appears, on word boundaries, in any
t2_heldout or t3_heldout prompt.

## Seeds

`random.Random(seed)` per split, continuing the slice-41
sequence (15041–15045): t2_diagnostic 15046, t2_heldout 15047,
t3_diagnostic 15048, t3_heldout 15049. Regeneration with the same
generator is byte-identical (md5-stable across two consecutive
runs; recorded in the slice-42 delivery note).

The generator seeds its prompt/derivation seen-sets from all six
slice-41 files on disk before generating, so no slice-41 prompt
or derivation can recur in the new batteries, and the four new
splits are mutually deduped by the same shared sets.

## Verification

`verify_batteries2.py` is an independent re-check (imports
nothing from the generator), mirroring `verify_batteries.py`:

- exact counts and per-category balance; split fields; the
  required prompt suffix; every answer integral or exact
  2-decimal;
- every derivation recomputed with the same restricted AST
  evaluator and compared to the stored answer;
- prompt uniqueness within each new file and across **all ten**
  battery files (slice 41 + slice 42); derivation uniqueness
  across all seven arithmetic files;
- heldout marker hygiene against both marker files (above);
- every weekday_offset prompt states the mapping, and the
  weekday it states for its date is the true 2025 weekday
  (recomputed from the parsed date);
- **prompt-parsing recompute (anti-circularity):** fresh
  regex/datetime logic extracts dates, spans and conversions
  from the prompt TEXT alone — never the derivation — and the
  parsed answer must equal the stored answer. The run FAILS if
  coverage is below 60% for either family. Current regeneration:
  t2 180/180 (100.0%), t3 180/180 (100.0%).

Its output is saved in `batteries/VERIFY2.txt`; exit code 0 iff
PASS. The slice-41 verifier and batteries are untouched and
still PASS.

## Scoring

`score.py` registers the four new splits additively —
`t2_diagnostic`, `t2_heldout`, `t3_diagnostic`, `t3_heldout` —
as arithmetic splits with `max_new_tokens` 96, files under
`batteries/` (diagnostics) and `private/` (heldouts). No existing
split's behaviour, constants or scoring code paths changed;
`score.py --selftest` still PASSes (54 cases). Scoring semantics
are the slice-41 arithmetic semantics: extract the LAST number in
the completion, correct iff within 0.011 of gold (exact for
integers, one cent of slack). Note for weekday_offset and the
add_days_count month variant, the gold is a small number (1–12)
by design — that is the task, and the LAST-number rule applies
unchanged.

## Commands

Regenerate and verify (Oracle, stdlib only):

    cd experiments/wsp
    python3 gen_batteries2.py
    python3 verify_batteries2.py | tee batteries/VERIFY2.txt
    python3 verify_batteries.py          # slice 41, still PASS
    python3 score.py --selftest          # still PASS

Score (Thor):

    python3 score.py --model DIR --split t2_heldout --out results/e5-t2.json

## Ambiguities resolved by the battery seat

1. **month_span** "whole months" is undefined in the brief; the
   complete-calendar-month ("birthday") rule above was chosen,
   is stated in every month_span prompt, and is the rule the
   verifier's parser applies.
2. **add_days_count, end-of-month variant:** "days to the end of
   the month" excludes the start date itself (a date on the 17th
   of a 31-day month has 14 days left); stated in the prompts.
3. **Derivation form for date answers:** golds are computed with
   `datetime`, but derivation strings must remain in the
   slice-41 restricted arithmetic language so the existing
   evaluator discipline carries over; calendar quantities are
   encoded as day-of-year / month / days-in-month operands.
4. **Exact 2-decimals in t3:** quarter-offset divisions by 100 /
   1000 (x.25 / x.5 / x.75 endings) are the only non-integer
   golds; nothing with a longer decimal expansion is generated.
