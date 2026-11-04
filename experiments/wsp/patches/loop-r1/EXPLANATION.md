# EXPLANATION — Jacquard Phase 15, E6 teacher–student loop, ROUND 1 patch

Student: Qwen3-0.6B (bf16, tied embeddings, hidden 1024, 751,632,384
parameters), input `~/wsp-exp/work/student-base` (sha256
f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b —
re-verified unchanged after all work; the patch was built only on copies).
Artefacts in this directory: `patch.py` (data-driven applier:
`--model-in/--model-out/--edits`, `--exclude`, `--exclude-critical`,
`--exclude-random-count`), `edits.json` (44 records), `gen_edits.py`,
`probe_mhat.py`, `patched-round1/` (the full patch), score/receipt files.

**Result: round1_diag 85.0% (51/60, base) → 90.0% (54/60, full patch).**
Receipt: 44 records applied, **41,398 scalars changed = 0.005508%** of
751,632,384 (bound 0.1% = 751,632). Regression split (slice-41
`diagnostic`, 80 items): **78.75% (63/80, base, re-measured by me) →
83.75% (67/80, patched)**.

---

## 1. Diagnosis of the 9 round-1 failures (from diag_export.jsonl raw outputs)

| Class | Count | Items | Evidence |
|---|---|---|---|
| Format/completion — verbose essay truncated at the 96-token cap | 6 | r1diag-001, 002, 003, 005, 007, 008 (all addsub_chain) | Every intermediate step on the page is arithmetically CORRECT (9981, 124, 5612, 4922, 7833, 1137…). The model ignores "Answer with just the number", writes a LaTeX/markdown worked solution, and runs out of tokens mid-final-step; the last-number extractor reads a partial digit ("…= 7") or an operand (409). The algorithm is present; the answer never lands. |
| Format/extraction — correct comparison buried in a sentence frame | 1 | r1diag-056 | "4268 is larger than 4075." — content correct, but the last number in the text is the *smaller* one, so the scorer reads 4075. First-token probe: the model already opens with the correct digit '4' (gap 0.0) — this is purely a trailing-frame failure. |
| Procedure / arithmetic content | 2 | r1diag-020, r1diag-026 | Completed outputs with wrong values: 91×56 stated as 5104 (gold 5096); 539/7 stated as 77.2857 (gold exactly 77). No format problem — the computation itself is wrong. Per the shared slice-42 finding (13 bias variants, zero yield on procedure/factor failures), NO edit in this patch claims to fix these. |

Headline: 7 of 9 failures (78%) are format/completion, concentrated in
addsub_chain (2/8 at base) — the same family failure as slice 41, but the
category mix differs: compare is 6/7 at base here (vs 5/10 on the slice-41
split), so there is far less compare headroom and, it turns out, far less
compare *tolerance* (see §3).

First-token probe (my own measurement on the 60 round-1 prompts,
`probe_mhat.py`): the failing addsub items open with "We" while the best
digit sits 2.25–6.25 logits behind; the direction geometry from the
family knowledge reproduces on this round — mean final-hidden-state
projection h·m̂ = **132.55** (range 115.24–143.36), mean cos(h, m̂) =
0.902. A shared additive offset along m̂ is therefore an almost
context-independent logit bias at answer initiation, as claimed in
slice 41.

## 2. Critical group A — `digit-first-answer-bias` — edits C1–C10 + twins C1T–C10T, CRITICAL

Rows 15–24 (tokens '0'–'9') of the tied embedding, each row +=
(2.75/132.55)·m̂_round1 (m̂ measured by `probe_mhat.py` on this round's
60 prompts; delta bf16-rounded and stored exactly in edits.json).
Both stored copies (`model.embed_tokens.weight` AND `lm_head.weight`)
are edited identically — the checkpoint stores the tied embedding
twice; editing one copy silently unties the head.

Mechanism claim: the identical offset adds ≈ +2.75 logits to every digit
at answer initiation without changing digit-vs-digit differences on the
output side, flipping the style prior from essay to compact arithmetic
on the items whose digit gap the dose covers, so answers land inside
the token cap. On the input side the same offset is a constant
digit-channel shift — and this is also the group's failure mode at
higher doses (§3).

## 3. Dose finding — the slice-41 optimum (+5) does NOT transfer; +2.75 chosen on two instruments

Trialled variants, all with the ' than' edit unless noted, scored on
round1_diag (base 85.0%):

| Variant | round1_diag | Notes |
|---|---|---|
| digit +1.5 | 86.7% | addsub 3/8 |
| digit +2.0 | 86.7% | addsub 3/8, one mul_2x2 flip (018) |
| digit +2.5 | 90.0% | addsub 5/8, one mul_2x2 flip (018) |
| **digit +2.75** | **90.0%** | addsub 5/8, compare 6/7, div 8/8; diagnostic-split 83.75% |
| digit +3.0 | 90.0% | identical round-1 failure set to +2.75; diagnostic-split 83.75% |
| digit +3.0, no ' than' | 88.3% | compare 5/7 — isolates the ' than' contribution (+1 compare item) |
| digit +3.5 | 83.3% | compare collapses to 2/7 |
| digit +5.0 (slice-41 dose) | 81.7% | addsub best (7/8) but compare 1/7, pct 6/7 |
| digit +5.0 + than | 83.3% | compare still 2/7 |
| digit +7.0 + than | 83.3% | compare 2/7 |
| ' than' only | 83.3% | compare 5/7 — fixes 056 but breaks 055/057 frame variants |

Why higher doses fail HERE: at +5 the patched model states the smaller
number as the greater one on r1diag-054/058/059/060 ("595 is greater
than 9688. Answer: 595") — compare *content* inverts, the opposite of
the slice-41 split's behaviour at the same dose. The plausible mechanism
is the tied input side: compare prompts are digit-dense, and the shared
digit-channel offset perturbs the latent comparison once it grows past
≈ +3. Whatever the mechanism, the dose–response on this round is a
cliff between +3.0 and +3.5, not the slice-41 plateau. I chose +2.75 —
the weakest dose reaching 90.0% on round1_diag AND 83.75% on the
diagnostic regression split (identical failure sets to +3.0 on both
instruments; +2.5 reaches 90.0% on round-1 but only 80.0% on the
diagnostic split, so it was rejected on the second instrument, not on
the tuning split alone).

## 4. Critical group B — `compare-frame-break` — edit C11 + twin C11T, CRITICAL

Row 1091 (token ' than'), scaled ×0.75, both stored copies.
Mechanism claim (from slice 41, re-verified here): after the model
states the larger number, the canned frame "…is larger than Y" drags
the smaller number into last position; weakening ' than' lets the
sentence end on the stated number ("4268 is larger." — r1diag-056 and
057 under the full patch). Isolated contribution at dose +3.0: compare
5/7 → 6/7 (88.3% → 90.0%). Claimed scope is the frame only, never
comparison content (see 055 below).

## 5. Non-critical group — `control-rows-predicted-inert` — edits N1–N11 + twins, NON-CRITICAL

Rows 151646–151656 (reserved special/vision tokens this text model
never emits), each += the identical delta vector as the digit rows:
same tensor, op, value and record count as the critical digit group,
differing only in which tokens they touch. Stated prediction, made
before final scoring: inert. Verified: the full patch (with controls)
scores identically to the core-only trial (without controls) on both
splits — same accuracy, same failure sets.

## 6. Self-ablation (all built with patch.py from the final edits.json, scored on round1_diag)

| Model | round1_diag | Reading |
|---|---|---|
| Base | 85.0% (51/60) | — |
| **Full patch** | **90.0% (54/60)** | fails: 005, 007, 008, 020, 041, 055 |
| Minus-critical (controls only, `--exclude-critical`) | 85.0% (51/60) | per-category AND failure set **identical to base** — the critical group carries the entire effect |
| Minus-random (`--exclude-random-count 22 --random-seed 20261103`; excluded 12 critical + 10 control records, incl. one twin of several digit rows and the embed copy of C11) | 86.7% (52/60) | removing half the records at random degrades the effect most of the way back to base (+1.7 of the +5.0 retained) |
| Minus-noncritical (core only = trials/edits_g275t build) | 90.0% (54/60) | identical to full — controls inert, as predicted |

## 7. Regression check — slice-41 `diagnostic` split (80 items)

Base 78.75% (63/80, re-measured) → patched 83.75% (67/80), +5.0 points.
Per category (base → patched, /10): addsub_chain 3→4, compare 5→9,
div_exact 10→10, mul_2x1 10→10, mul_2x2 7→6, pct_of 10→10,
unit_price 8→9, word_2step 10→9. Net +4 items; the two single-item
regressions (mul_2x2 diag-058 gained as a failure, word_2step swap) are
the same near-tie flip collateral seen on round-1 (041), reported, not
hidden.

## 8. What remains broken under the full patch (round1_diag, 6 fails)

- r1diag-005, 007, 008 — addsub essays whose style prior survives
  +2.75; they now truncate a few tokens later, intermediates still
  correct. The dose that would flip them (+5) costs more in compare
  content than it buys — a real trade-off frontier, measured in §3.
- r1diag-020 (91×56) and the div item's siblings — arithmetic content;
  no claim. (r1diag-026 itself happens to pass under the patch —
  "539 divided by 7 is 77" — a style side-effect, not a taught
  procedure; I do not count it as a procedure fix.)
- r1diag-041 (word_2step) — collateral flip: 154 + 44 stated as 200
  under the patch (passed at base). 
- r1diag-055 (compare) — honest exposure, not a regression in content:
  at base the model already *said* "1029 is larger than 8115" and
  passed only because the extractor reads the last number; with the
  frame broken it says "1029 is larger." and its (always-wrong)
  comparison content is what gets scored.

## 9. Predicted held-out effect (stated before coordinator scoring)

Two instruments agree at +5.0 points (round1_diag 85.0→90.0, n=60;
diagnostic 78.75→83.75, n=80, disjoint items), driven by template-level
mechanisms (essay truncation in addsub, the compare sentence frame)
rather than item memorisation, and the dose was chosen at the weak end
of the effective plateau with compare content intact on both
instruments. Discounts: the gain was selected on round1_diag; single
items flip either way at this dose (±1–2 items per 60); the held-out
addsub share and its essay-style fraction are unknown to me.

**Prediction: +4 points on held-out (range +2…+6), i.e. ≈ 84.5%
against the 80.5% base** — roughly a fifth of the 19.5-point
teacher gap. Not more: the remaining round-1 failures are dominated by
content errors (arithmetic slips, latent comparison errors, one
stubborn essay sub-population) that this patch family measurably
cannot reach.
