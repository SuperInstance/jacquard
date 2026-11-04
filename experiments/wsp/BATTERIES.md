# Phase 15 Batteries — Design Document

Instruments for the weight-space programming experiments
(PLAN.md, slice 41). Built by the battery seat; the patcher never
builds or edits these files. Generation is seeded (fixed seeds,
Python stdlib `random`); scoring is code-only (no model judges
any score). Scoring uses greedy decoding — see the determinism
caveat under Scoring: greedy is not bitwise reproducible across
batch compositions / hardware, and results may move by plus or
minus an item between runs.

## Files

| file | items | visibility |
|---|---|---|
| `batteries/diagnostic.jsonl` | 80 arithmetic | patcher-visible (items + base outputs) |
| `batteries/validation.jsonl` | 200 arithmetic | patcher sees per-category aggregates only |
| `private/heldout.jsonl` | 200 arithmetic | patcher never sees items or scores until the coordinator scores a finished patch |
| `private/forget_instr.jsonl` | 100 format checks | patcher never sees any item |
| `private/forget_fact.jsonl` | 100 factual QA | patcher never sees any item |
| `private/forget_prose.jsonl` | 24 paragraphs | patcher never sees any item |
| `batteries/setA_markers.json` | 47 markers | generated; verifier input |
| `batteries/VERIFY.txt` | — | saved output of the verifier |

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
  {2, 4, 5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 80, 90};
  bases are multiples of 100/gcd(100, percent) (the smallest step
  that makes the result an integer), up to 400.
- `word_2step` — two-operation word problems (spend-and-change,
  read-and-remainder, buy-twice totals). In the change subtype the
  note denomination is the smallest of 50/100/200 that is >= the
  total cost, so change is never negative; the verifier asserts
  every `word_2step` gold is >= 0.
- `unit_price` — total price ÷ count; the only category whose
  answers may be non-integer: exact 2-decimal money values.
- `compare` — return the larger of two numbers. This holds for
  BOTH template sets: set B's compare is max-of-two only (an
  earlier version also used smaller-of-two and largest-of-three;
  that made set B non-comparable with set A and was removed).

Item shape: `{"id", "split", "category", "prompt", "answer",
"derivation"}`. `answer` is a JSON number. `derivation` is the
worked expression (e.g. `6692 + 957 - 4538`, `max(48, 35)`,
`7.50 / 3`) and exists for graders only — it is never shown to a
model. Every prompt ends with the sentence
"Answer with just the number."

Uniqueness is enforced on two keys, across all three arithmetic
splits: no prompt string repeats, and no derivation string
repeats (a shared seen-set for derivations in the generator;
resampling on collision). Instance leakage through a repeated
worked example with different surface numbers is therefore
excluded by construction, not just by prompt wording.

### Bare symbolic forms

Five categories (addsub_chain, mul_2x1, mul_2x2, div_exact,
pct_of) have a bare symbolic form ("Compute: 6692 + 957 − 4538.",
"What is 42 * 7?", "42 * 7 equals what?", "25 percent of 200
equals what?", …). In both template sets the generator alternates
bare / non-bare deterministically within those categories, so
each split lands in the same 25–35% band overall. Realised
shares in the current regeneration (counted by the verifier):

- diagnostic: 25/80 (31.2%)
- validation: 65/200 (32.5%)
- heldout: 66/200 (33.0%)

(An earlier heldout set had only ~10/200 bare items against
66/200 in validation — a comparability defect, now fixed.)

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
"percent"). Set B mirrors set A's operation mix: compare is
max-of-two only, and set-B `word_2step` covers the same three
subtypes as set A — spend-and-change, reading-remainder and
buy-twice total — chosen uniformly (realised heldout counts:
8 change / 7 reading-remainder / 10 buy-twice of 25).

Marker hygiene (revised): the generator emits
`batteries/setA_markers.json` containing ALL pool-A strings
(8 names + 8 objects + 3 shops) plus 28 set-A template frame
fragments ("Compute:", "What is", "Multiply", "Divide", "% of",
"packs of", "rows of chairs", "ride the bus", "Which is larger",
…) — 47 markers in total. The verifier loads that file (there is
no hand-maintained marker list in the verifier any more) and
asserts no marker appears in any heldout prompt. Appearance is
word-boundary based: a marker must occur as a whole word or
phrase, so pool-B "notebooks" is not a hit for pool-A "books".

### Seeds

`random.Random(seed)` per split: diagnostic 15041, validation
15042, heldout 15043, forget_instr 15044, forget_fact 15045.
forget_prose is fixed inline text. Regeneration with the same
generator is byte-identical (verified by re-running the generator
and comparing hashes).

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
fruits, describe a cat in 5–10 words, …). Every topic pool has at
least as many entries as the maximum number of draws of its type,
so no prompt repeats within the file (the verifier now asserts
within-file uniqueness for every file, which caught a wrap-around
duplicate here).

### forget_fact (100)

Item: `{"id", "category", "prompt", "answer", "aliases"}` from
fixed tables authored in gen_batteries.py: world capitals (30),
chemical element symbols (25), solar-system facts (15), exact unit
conversions (14), animal/geography misc (16 — the hexagon-sides
item lives here, not in conversions; it is a shape fact, not a
unit conversion). Scoring is token-boundary matching (see
Scoring): output and candidate are lowercased, punctuation
becomes spaces, whitespace collapses; a hit is the normalised
answer or an alias appearing as a complete token, or as a
complete multi-token phrase, in the normalised output. Substring
containment no longer counts.

Alias audit: aliases must never credit a reply that has not
actually produced the answer. Removed:

- the element-NAME aliases on symbol questions — "aluminum" for
  Al and "sulfur" for S (a model echoing the element name, in
  either spelling, has not produced the symbol);
- "one" for the gold "1" (a generic pronoun, usable in almost
  any sentence).

Remaining aliases are distinctive proper-name shortenings or
spelling variants (Delhi, Berne, Brasília, Reykjavík, Pacific,
Nile, Sahara, Sun, Moon, Milky Way), specific multi-token phrases
("100 cm", "60 minutes", "a giraffe", …), or number words that are
the numeric gold itself in word form (six, eight, ten, three,
four) — each of which can only match as a whole token/phrase
under the token-boundary rule, and none of which is a generic
English filler word or a substring hazard.

### forget_prose (24)

24 paragraphs of neutral descriptive prose, 60–90 words each,
written inline in the generator; item shape is exactly
`{"id", "text"}`. Scored by mean token NLL, teacher-forced over the
raw text (no chat template, no generation): for each token after
the first, the negative log-probability under the model, averaged
over the paragraph; the split score is the mean over paragraphs.

## Verification

`verify_batteries.py` is an independent re-check (it imports
nothing from the generator):

- it reparses every arithmetic derivation with a restricted AST
  evaluator (+ − × ÷, parentheses, numeric literals, max/min),
  recomputes it, and compares against the stored answer (exact
  for integers, |diff| ≤ 0.005 for money);
- **prompt-parsing recompute (anti-circularity):** fresh
  regex/pattern logic in the verifier extracts numbers and
  operations from the prompt TEXT itself (bare symbolic forms,
  pct_of, div_exact, the mul forms, the main addsub frames, the
  word_2step and unit_price frames, compare) — never the stored
  derivation — and asserts the prompt-parsed answer equals the
  stored answer for every item it can parse. The run FAILS if
  parse coverage is below 60% of arithmetic items. Current
  regeneration: 463/480 parsed (96.5% coverage), all matching;
- exact counts and per-category balance, the required prompt
  suffix, all `word_2step` golds >= 0, bare-form share in the
  25–35% band per arithmetic split;
- prompt uniqueness across all six files AND within each file
  (unique-prompt count == item count per file);
- heldout marker hygiene against the generator-emitted
  `batteries/setA_markers.json` (see above);
- the structural rules for the forgetting batteries.

Its output is saved in `batteries/VERIFY.txt`; exit code 0 iff PASS.

## Scoring

`score.py` runs on the Thor GPU (transformers, bf16; CUDA if
available, else CPU). Chat template applied with thinking disabled
(`apply_chat_template(..., enable_thinking=False)`). If a
tokenizer rejects that keyword, the harness now raises a clear
TypeError and stops — an instrument must fail loudly, never
silently change the prompt by falling back. Generation passes
`eos_token_id` explicitly: the union of the eos ids in the model
directory's `generation_config.json` (if present) and the
tokenizer's eos id (a single int when the union has one element,
a list otherwise). Greedy decoding, batch 16, max_new_tokens:
arithmetic 96, forget_instr 128, forget_fact 32. Battery paths
resolve relative to score.py itself.

Determinism caveat: decoding is greedy with no sampling, but
that is not a guarantee of identical results on every run —
batch composition and hardware numerics may move a borderline
item, so treat scores as reproducible to within plus-or-minus
an item between runs, not as bitwise fixed.

Arithmetic scoring: extract the LAST number in the completion
(numeric regex; commas removed, surrounding $, % and prose
ignored; leading-dot decimals such as ".75" and "$.75" extract
as 0.75); correct iff |extracted − gold| ≤ 0.011, which is exact
for integer answers and allows one cent of slack on money.
Known extraction edges (documented, rule deliberately unchanged):
fractions such as "1/2" extract their last component number;
ranges extract their last endpoint; and any trailing incidental
number in a reply (a year, a page number, a restated operand
after the answer) wins under the LAST-number rule.

Fact scoring: token-boundary matching as described under
forget_fact. Adversarial cases pinned in the selftest, all of
which must NOT match: "The chemical symbol for carbon is Fe"
vs gold "C"; "I do not know" vs "H"; "Earth has 12 moons" vs
"1"; "No comparison is possible" vs "Paris" ("paris" is only a
substring of "comparison"). Short candidates (< 3 characters:
element symbols, small counts) match only as whole tokens.

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
model) and prints PASS/FAIL per case, including the leading-dot
extraction cases and the adversarial fact-matching cases above.

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
