# Phase 15 Batteries — Design Document

Instruments for the weight-space programming experiments
(PLAN.md, slice 41). Built by the battery seat; the patcher never
builds or edits these files. Everything is deterministic and
seeded; scoring is code-only (no model judges any score).

## Files

| file | items | visibility |
|---|---|---|
| `batteries/diagnostic.jsonl` | 80 arithmetic | patcher-visible (items + base outputs) |
| `batteries/validation.jsonl` | 200 arithmetic | patcher sees per-category aggregates only |
| `private/heldout.jsonl` | 200 arithmetic | patcher never sees items or scores until the coordinator scores a finished patch |
| `private/forget_instr.jsonl` | 100 format checks | patcher never sees any item |
| `private/forget_fact.jsonl` | 100 factual QA | patcher never sees any item |
| `private/forget_prose.jsonl` | 24 paragraphs | patcher never sees any item |

The `private/` directory is the enforcement boundary: held-out and
forgetting material lives only there.

## Arithmetic batteries

Eight categories, exactly equal proportions (diagnostic 10 each,
validation 25 each, heldout 25 each):

- `addsub_chain` — a + b − c chains; add/sub operands up to 4 digits.
- `mul_2x1` — two-digit × one-digit multiplication.
- `mul_2x2` — two-digit × two-digit, up to 99×99.
- `div_exact` — division constructed from divisor × quotient, so the
  quotient is always an integer.
- `pct_of` — percentage of a base; percent from
  {5, 10, 15, 20, 25, 50, 75}; bases chosen in multiples that make
  the result an integer.
- `word_2step` — two-operation word problems (spend-and-change,
  read-and-remainder, buy-twice totals).
- `unit_price` — total price ÷ count; the only category whose
  answers may be non-integer: exact 2-decimal money values.
- `compare` — return the larger (set A / most of B) or smaller of
  two numbers, or the largest of three (set B).

Item shape: `{"id", "split", "category", "prompt", "answer",
"derivation"}`. `answer` is a JSON number. `derivation` is the
worked expression (e.g. `6692 + 957 - 4538`, `max(48, 35)`,
`7.50 / 3`) and exists for graders only — it is never shown to a
model. Every prompt ends with the sentence
"Answer with just the number."

### Template set A vs set B

Diagnostic and validation use template set A with lexical pool A
(names Maya, Liam, Sofia, Noah, Ava, Ethan, Mia, Lucas; objects
marbles, stickers, pencils, apples, books, trading cards, shells,
buttons; shops corner shop, market stall, school store). Heldout
uses template set B with lexical pool B (names Priya, Kenji, Olga,
Mateo, Ingrid, Tariq, Nadia, Felix; objects bolts, ribbons, stamps,
peaches, notebooks, tokens, beads, coins; shops harbour kiosk,
night market, village bakery). Set B is separate generator code
(`b_*` functions in gen_batteries.py), not parameter tweaks of set
A: different sentence frames ("Beginning from N, increase by …",
"Split N into D equal parts", percentages spelled out as
"percent", three-number comparisons, smaller-of-two comparisons).
The verifier asserts that no heldout prompt contains any set-A-only
marker phrase (a defined list including "Compute:", "What is",
"Multiply", "Divide", "% of", "packs of", all pool-A names,
objects and shops).

### Seeds

`random.Random(seed)` per split: diagnostic 15041, validation
15042, heldout 15043, forget_instr 15044, forget_fact 15045.
forget_prose is fixed inline text. Regeneration is byte-identical
(verified by re-running the generator and comparing hashes). The
generator also enforces that no prompt string repeats anywhere
across the three arithmetic splits (resampling on collision).

## Forgetting batteries

### forget_instr (100)

Item: `{"id", "category", "prompt", "check"}` where category is
the check type. Six check types, cycled evenly (16–17 items each):

- `json_key {key}` — the reply parses as a JSON object containing
  the key. The scorer tries the whole stripped reply first, then
  the substring from the first `{` to the last `}`.
- `all_caps` — stripped reply is non-empty, contains at least one
  letter, and equals its own upper-case form.
- `starts_with {word}` — stripped reply starts with the word,
  case-sensitive, followed by a non-letter or end of text.
- `ends_with {word}` — the last whitespace-separated token of the
  stripped reply, with trailing punctuation removed, equals the
  word.
- `bullets3` — exactly 3 non-empty lines, every one starting
  with "- ".
- `word_count_range {lo, hi}` — word count of the reply
  (whitespace split) lies in [lo, hi].

All prompts are simple content requests a small model can satisfy
in principle (name a colour as JSON, shout a phrase, list three
fruits, describe a cat in 5–10 words, …).

### forget_fact (100)

Item: `{"id", "category", "prompt", "answer", "aliases"}` from
fixed tables authored in gen_batteries.py: world capitals (30),
chemical element symbols (25), solar-system facts (15), exact unit
conversions (15), animal/geography misc (15). Aliases cover
case/plural/spelling variants. Scoring is normalised containment:
output and candidate are lowercased, punctuation becomes spaces,
whitespace collapses; a hit is the normalised answer or any alias
appearing as a substring of the normalised output.

### forget_prose (24)

24 paragraphs of neutral descriptive prose, 60–90 words each,
written inline in the generator; item shape is exactly
`{"id", "text"}`. Scored by mean token NLL, teacher-forced over the
raw text (no chat template, no generation): for each token after
the first, the negative log-probability under the model, averaged
over the paragraph; the split score is the mean over paragraphs.

## Verification

`verify_batteries.py` is an independent re-check (it imports
nothing from the generator): it reparses every arithmetic
derivation with a restricted AST evaluator (+ − × ÷, parentheses,
numeric literals, max/min), recomputes it, and compares against the
stored answer (exact for integers, |diff| ≤ 0.005 for money); it
asserts exact counts and per-category balance, the required prompt
suffix, prompt uniqueness across all six files, heldout marker
hygiene, and the structural rules above. Its output is saved in
`batteries/VERIFY.txt`; exit code 0 iff PASS.

## Scoring

`score.py` runs on the Thor GPU (transformers, bf16; CUDA if
available, else CPU). Chat template applied with thinking disabled
(`apply_chat_template(..., enable_thinking=False)`, guarded with a
fallback for tokenizers that reject the kwarg). Greedy decoding,
batch 16, max_new_tokens: arithmetic 96, forget_instr 128,
forget_fact 32. Battery paths resolve relative to score.py itself.

Arithmetic scoring: extract the LAST number in the completion
(numeric regex; commas removed, surrounding $, % and prose
ignored); correct iff |extracted − gold| ≤ 0.011, which is exact
for integer answers and allows one cent of slack on money.

Output JSON: per split — overall accuracy (or `mean_nll` for
prose), per-category accuracy, and per-item records
`{id, category, gold, raw_output, extracted, correct}`. For
forget_instr, `gold` is the check object and `extracted` is null;
for forget_fact, `extracted` is null; for prose, `gold` is null,
`extracted` is the paragraph's mean NLL, `correct` is null.

`score.py --inspect --model DIR` prints a config summary as JSON
(layers, hidden size, vocab, tied embeddings, attention heads,
parameter count — the count is summed from safetensors headers,
no full model load).

`score.py --selftest` exercises the pure extraction / checker /
fact-matching / NLL helpers on synthetic cases (no torch, no
model) and prints PASS/FAIL per case.

## Commands

Regenerate and verify (Oracle, stdlib only):

    cd experiments/wsp
    python3 gen_batteries.py
    python3 verify_batteries.py | tee batteries/VERIFY.txt

Score (Thor):

    python3 score.py --model ~/wsp-exp/models/Qwen3-0.6B \
        --split all --out results/base-all.json
    python3 score.py --inspect --model ~/wsp-exp/models/Qwen3-0.6B
    python3 score.py --selftest

## Split discipline

- The patcher works only from diagnostic items (+ base outputs)
  and validation per-category aggregates.
- Heldout and all forgetting batteries are coordinator-only until
  a finished patch is scored; E6 uses this same heldout split,
  answered by a teacher session that never patches.
- Anyone changing a battery must regenerate, re-verify, and note
  the change in the phase log; a changed battery invalidates
  comparisons against earlier scores.
