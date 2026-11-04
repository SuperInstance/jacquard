# EXPLANATION — Jacquard Phase 15, E6 teacher–student loop, ROUND 2 patch

Student in: the ADOPTED round-1 model `~/wsp-exp/loop/round1/patched-round1`
(held-out 85.5%, round2_diag 81.7% = 49/60). This patch is authored ON TOP
of it; the input directory was only ever read (patch.py copies before
writing). Artefacts in this directory: `patch.py` (the round-1 data-driven
applier, copied verbatim), `edits.json` (26 records), `gen_edits_r2.py`,
`probe_r2.py` + `probe_mhat_r2.pt` + `probe_first_token_r2.json`,
`patched-round2/` (full patch), `patched-minus-critical/`,
`patched-minus-random/`, `patched-minus-noncritical/`, receipts and score
files, `trials/` (variant edits + scores + receipts; trial model dirs
deleted after scoring).

**Result: round2_diag 81.7% (49/60, adopted) → 91.7% (55/60, full patch),
zero items lost.** Regression instruments: `diagnostic` 83.75% (67/80,
adopted, re-measured by me) → **88.75% (71/80)**, zero lost; `round1_diag`
**90.0% (54/60) → 90.0% (54/60)**, churn +2/−2 (see §7). Scalars changed
by this round's patch: **24,724 = 0.003289%** of 751,632,384 (bound
0.1% = 751,632); the critical group alone touches 4,096 scalars.

---

## 1. Diagnosis of the 11 round-2 failures (from diag_export.jsonl raw outputs)

| Class | Count | Items | Evidence |
|---|---|---|---|
| Format/completion — verbose essay truncated at the 96-token cap | 6 | r2diag-001, 003, 005, 007 (addsub_chain, all "Compute:" frame), 050 (unit_price), 054 (compare) | Every intermediate step on the page is arithmetically CORRECT (7495→"…= 2", 6229→"…= 8", 7726→"…= 4", 5188→"…= 9" — all four Compute essays are exactly 165 chars and are cut mid-final-answer, the correct first digit already written). 050 sets up the right division 181.50/11 and is cut at "Cost per card = ". 054's digit-by-digit reasoning concludes correctly (1399 smaller) and is cut before stating 5973. The algorithm is present; the answer never lands inside the cap. |
| Procedure — operation-sign error in word problems | 2 | r2diag-004, 006 (addsub_chain word frame) | Both complete, both ADD the sold amount: "455 + 262 + 452 = 1169" (gold 645) and "104 + 32 + 498 = 634" (gold 570, prose even says "add … the sold during the day"). The arithmetic on the wrong expression is exact. No format problem. |
| Content — arithmetic slips | 2 | r2diag-017, 021 (mul_2x2) | Digit-first, complete, wrong values: 76×71 stated 5356 (gold 5396); 61×73 stated 4543 (gold 4453, middle digits transposed). |
| Content — comparison inversion | 1 | r2diag-056 (compare) | "3277 is larger." — digit-first already (first-token probe: '3' is argmax, gap 0.0); the latent comparison error round 1 reported, in the open. |

Contrast with round 1: the failure mass has moved. Round 1 was 7/9
format; round 2 is 6/11 format, but the format failures are now a
*residual sub-population* — the essays whose style prior survived the
+2.75 digit dose — plus a newly visible content block (2 sign errors,
2 mul slips, 1 inversion = 5/11) that no bias lever in this family
reaches (slice-42: 13 variants, zero yield on procedure/knowledge).

## 2. New structure this round offers: the essay basin has named doors

First-token probe on the adopted model over the 60 round-2 prompts
(`probe_r2.py`; geometry reproduces: h·m̂ mean 132.50, range
117.00–144.10, mean cos 0.904). On the six truncation items the argmax
is an essay opener, and in every case the SAME two tokens hold the door:

| Item | Argmax | Best digit | Gap | Runner-up openers |
|---|---|---|---|---|
| 001 | 'We' 27.63 | '7' 26.75 | 0.88 | 'To' 26.75, 'Compute' 25.38 |
| 003 | 'We' 28.13 | '5' 26.25 | 1.88 | 'To' 26.75 |
| 005 | 'We' 27.75 | '6' 27.38 | 0.38 | 'To' 26.25 |
| 007 | 'We' 28.00 | '4' 26.50 | 1.50 | 'To' 26.25 |
| 050 | 'We' 26.25 | '1' 20.38 | 5.88 | 'To' 25.75, 'Luc' 25.75 |
| 054 | 'To' 26.00 | '5' 25.63 | 0.38 | 'The' 25.25 |

"We are given the expression…", "We are told…", "To determine which
number is greater…" — the truncating essays enter through 'We' and 'To'.
That makes a lever available that is **different in kind** from round
1's: suppress the two opener rows instead of raising the digit rows.
Digit rows are not touched at all, so the tied input-side digit-channel
shift — the mechanism that inverts compare content past dose ≈ +3 — does
not grow; and 'We'/'To' occur in none of the 60 prompts as input tokens,
so the input-side exposure of this edit is near zero on this battery
family (checked in the prompt tokenisations implicit in the probe: the
prompts are digit/word-problem text with no sentence-initial 'We'/'To').

Risk stated in advance: 19/60 items have argmax 'We' or 'To', 13 of them
currently CORRECT (div/pct/unit_price/compare essays short enough to
complete). Suppressing the openers re-routes those items to their
runner-up paths (digit-first, prompt-name-first, 'Since'-, 'The'-first);
each is a possible collateral flip. The trials in §4 are the measurement
of that risk, not an assumption that it is zero.

## 3. Critical group — `essay-opener-suppression` — edits C1, C1T, C2, C2T, CRITICAL

Rows 1654 ('We') and 1249 ('To') of the tied embedding, each row +=
−(2.0/132.50)·m̂_r2 (m̂_r2 = unit-normalised mean final hidden state at
answer initiation of the ADOPTED model over the 60 round-2 prompts,
measured by `probe_r2.py`; delta bf16-rounded, stored exactly in
edits.json). Both stored copies (`model.embed_tokens.weight` AND
`lm_head.weight`) are edited identically — the checkpoint stores the
tied embedding twice.

Mechanism claim: at answer initiation the offset subtracts ≈ 2.0 logits
from 'We' and 'To' only, closing the 0.38–1.88-logit gaps on the
truncation items so generation enters the compact path (bare arithmetic
lines, or a short prompt-restating path) and the answer lands inside
the 96-token cap. Claimed scope is the opener choice only — never
arithmetic or comparison content. The two mul slips, the two sign
errors and the 056 inversion are predicted UNCHANGED, and are.

## 4. Trialled variants (all with control rows, scored on round2_diag; adopted = 81.7%)

| Variant | round2_diag | Gained | Lost |
|---|---|---|---|
| {'We','To'} β=2.0 | **91.7% (55/60)** | 001, 003, 005, 007, 050, 054 | none |
| {'We','To'} β=2.5 | 91.7% (55/60) | identical set | none |
| {'We','To'} β=3.0 | 91.7% (55/60) | identical set | none |
| {'We'} only β=3.0 | 90.0% (54/60) | 001, 003, 005, 007, 050 | none (054 kept, its opener is 'To') |

The dose–response is a flat plateau 2.0–3.0 with identical failure sets;
β=2.0 chosen as the weakest dose on the plateau (round-1 doctrine).
Surprises, recorded plainly: (a) 050 flipped at every β despite a
5.88-logit first-token gap — with 'We'/'To' suppressed it takes a
'Lucas paid…' restatement path that reaches "181.50/11 = 16.50" inside
the cap; the first-token margin did not predict this, the generation
did. (b) None of the 13 at-risk correct items flipped at any trialled
dose — their runner-up paths (prompt-name-first restatements, 'Since',
'The number … is greater than …. Answer: …') all complete correctly.
The flipped Compute items now answer as compact arithmetic, e.g. 001:
"7196 + 299 = 7495 \n7495 − 5144 = 2351 \n\nAnswer: 2351"; 054:
"5973 is greater than 1399. \n\nAnswer: 5973".

## 5. Non-critical group — `control-rows-predicted-inert` — edits N1–N11 + twins, NON-CRITICAL

Rows 151646–151656 (reserved special tokens this text model never
emits), each += the identical delta vector as the opener rows: same
tensor, op, value and matched construction as round 1's controls,
differing only in which tokens they touch. Stated prediction, made
before final scoring: inert. Verified twice (§6): minus-critical
(controls only) reproduces the adopted model exactly on round2_diag,
and minus-noncritical (core only) reproduces the full patch exactly.

## 6. Self-ablation (built with patch.py from the final edits.json, scored on round2_diag)

| Model | round2_diag | Reading |
|---|---|---|
| Adopted (input) | 81.7% (49/60) | fails: the 11 of §1 |
| **Full patch** | **91.7% (55/60)** | fails: 004, 006, 017, 021, 056 — exactly the content class |
| Minus-critical (controls only, `--exclude-critical`) | 81.7% (49/60) | failure set **identical to adopted, item for item** — the critical group carries the entire effect; controls inert |
| Minus-random (`--exclude-random-count 13 --random-seed 20261103`; kept records include C1 ('We', embed copy only) and C2T ('To', head copy only) + 11 controls) | 83.3% (50/60) | only 054 retained of the six gains — mechanistically tidy: a head-only 'To' edit still flips 054 (gap 0.38), while the embed-only 'We' edit changes no output logits and flips nothing |
| Minus-noncritical (core only) | 91.7% (55/60) | identical failure set to full — controls inert, as predicted |

## 7. Regression checks (adopted baselines re-measured by me this round; both reproduce the ledger: 83.75 and 90.0)

**`diagnostic` (slice-41, 80 items): 83.75% (67/80) → 88.75% (71/80), +5.0.**
Gained diag-005, 007, 009 (addsub_chain 4→7 of 10) and diag-022
(mul_2x2 6→7); lost NONE. compare holds 9→9. The opener lever
generalises to the split it was not tuned on, with zero collateral —
the strongest transfer evidence in this round's record.

**`round1_diag` (60 items): 90.0% (54/60) → 90.0% (54/60), net 0, churn 2+/2−.**
Gained r1diag-005 and r1diag-007 — precisely the two residual
"We are given the expression" truncations round 1's report named as
unreachable at the adopted dose ("the dose that would flip them costs
more in compare than it buys"); the opener lever reaches them without
touching the digit dose, and compare on this split holds 6→6. Lost:
r1diag-002 (word addsub: adopted path "We start with…" subtracted
correctly; the new 'The total number…' path writes 415 + 291 − 409 —
both signs flipped, the same sign-fragility family as r2diag-004/006)
and r1diag-018 (mul word problem: adopted 'To find…' essay computed
89×18 = 1602; the new 'The…' path slips to 1592). Both losses are
path-change collateral in the content class, reported, not hidden.

## 8. What remains broken under the full patch (round2_diag, 5 fails)

- r2diag-004, 006 — word-problem sign errors ("sold" added). The
  operation choice is unstable across style paths (see r1diag-002), i.e.
  it is content, not format; no opener/bias edit claims it.
- r2diag-017, 021 — mul_2x2 arithmetic slips on already-compact paths.
- r2diag-056 — comparison inversion, digit-first already; the latent
  comparison error. (054's frame is fixed by format; 056's content is
  not touched, by design and in fact.)

The reachable format mass on this round's battery is now exhausted:
every remaining failure is a completed output with wrong content.

## 9. Predicted held-out effect (stated before coordinator scoring)

Evidence: round2_diag +10.0 (n=60, zero losses), `diagnostic` +5.0
(n=80, zero losses, NOT tuned on), `round1_diag` 0.0 net with 2+/2−
churn. The mechanism is template-level (two opener tokens gate the
truncating essay family across all three splits), and the dose is the
weakest on a flat plateau. Discounts: the gain was selected on
round2_diag; held-out's residual essay population is unknown (round 1
already harvested part of it: adopted held-out is 85.5%, so fewer
truncations remain to flip than round2_diag's fresh mix suggests);
path-change churn of ±1–2 items per 60 was observed on round1_diag and
could net against the gain.

**Prediction: +3 points on held-out (range +1…+5), i.e. ≈ 88.5%
against the adopted model's 85.5%** — roughly 15% of the remaining
19.5-point teacher gap (cumulative gap closure ≈ 41% if it lands).
Not more: the remaining failures on every instrument I can see are
dominated by content errors (sign choice, mul slips, comparison
inversion) that this patch family measurably cannot reach, and I expect
the held-out residual mix to be similarly content-heavy.
