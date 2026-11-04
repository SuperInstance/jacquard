# EXPLANATION — Jacquard Phase 15, E6 teacher–student loop, ROUND 3 patch

Student in: the ADOPTED round-2 model `~/wsp-exp/loop/round2/patched-round2`
(held-out 87.5%, round3_diag 85.0% = 51/60). This patch is authored ON TOP
of it; the input directory was only ever read (patch.py copies before
writing). Artefacts in this directory: `patch.py` (the round-1 data-driven
applier, copied verbatim from round 2), `edits.json` (22 records, ZERO
critical), `gen_final_r3.py`, `gen_edits_r3.py` (trial generator),
`probe_r3.py` + `probe_mhat_r3.pt` + `probe_first_token_r3.json`,
`churn.py`, `patched-round3/` (the shipped build),
`patched-minus-critical/`, `patched-minus-random/`,
`patched-minus-noncritical/`, receipts and score files, `trials/`
(variant edits + scores + receipts; trial model dirs deleted after
scoring).

**Result: an EVIDENCED NEGATIVE.** The shipped patch is control-only —
the critical group is empty by design — with a prediction of exactly 0,
stated in `edits.json` before final scoring. It reproduces the adopted
model on every instrument (see §6, §7). Six distinct levers were trialled
first (§4); none beats 85.0% on round3_diag with a statable mechanism and
intact regressions. Round 3 therefore closes **0 points** of held-out gap
by prediction, and the loop's plateau condition (closure <2 points for 2
consecutive rounds: round 2 closed +2.0, round 3 closes 0) is met on the
teacher side of the record.

---

## 1. Diagnosis of the 9 round-3 failures (from diag_export.jsonl raw outputs)

| Class | Count | Items | Evidence |
|---|---|---|---|
| Content — arithmetic slip (completed, wrong value) | 4 | r3diag-001 (657−596+282: expression written correctly, result stated 245, gold 343; 81 tokens), r3diag-002 (1346−345 stated 991, gold 1001; digit-first, 36 tokens), r3diag-020 (28×86 stated 2428, gold 2408; digit-first, 12 tokens), r3diag-021 (98×73 stated 7194, gold 7154; 63 tokens) | The algorithm and the expression are right; the arithmetic on the page is wrong. No format problem: every one completes well inside the 96-token cap. |
| Procedure — operation-sign error | 1 | r3diag-005 | Adds the sold amount: "246 + 74 + 281 = 601" (gold 453); the arithmetic on the wrong expression is exact, output complete (52 tokens). Same family as r2diag-004/006, which round 2 already showed no bias lever reaches. |
| Content — comparison inversion | 3 | r3diag-055 ("4799 is larger", gold 7189; digit-first, first-token margin only 0.25 — '4' 28.0 vs '7' 27.75), r3diag-057 ("2423 is greater than 5305"; first digits '2' 25.25 vs '5' 25.125, a 0.125 margin, then the essay asserts the wrong one), r3diag-058 ("594 is larger", gold 5399; digit-first, emits the shorter number whole) | The latent comparison error, three times in one battery. Two of three are already digit-first — the decision itself is wrong at the first digit, not the format around it. No positional consistency to exploit: the model picks the first number (055), the second (057), and the shorter (058). |
| Format — cap truncation | 1 | r3diag-040 | The ONLY format failure. Output is exactly 96 tokens (probe-verified): the reasoning is fully correct (167 − 40 = 127 stated in the body) and generation is cut mid-answer at "**Answer: 1". It enters through a name-restatement path (first token 'S', of "Sofia" — a multi-token name, not a single suppressible opener row), with the best digit 4.75 logits behind. |

Contrast with rounds 1–2: the failure mass is now 8/9 content or
procedure on completed outputs. The one format item does not enter
through 'We'/'To' (round 2's doors, already suppressed) or through a
digit (28/60 items are already digit-first, probe-measured).

## 2. Probe geometry (adopted round-2 model, round3_diag prompts)

`probe_r3.py`: h·m̂ mean 133.66 (range 119.90–142.73), mean cos 0.902 —
the round-1/2 geometry reproduces on the new battery, so m̂-based trial
doses below are calibrated exactly as in prior rounds (dose β subtracts
≈β logits at answer initiation). First-token facts used in §1: 001 and
005 are 'The'-first (24.0 / 24.25, gaps 2.75 / 3.375 over the best
digit); 002, 020, 055, 058 are digit-first already (gap 0.0); 040 is
'S'-first with 'We' third at 23.375.

## 3. Critical group — NONE (declared in advance)

No critical edits are declared for round 3. Every candidate critical
group was trialled in §4 and failed at least one of the three gates a
real patch must pass: (i) beats 85.0% on round3_diag, (ii) by a
mechanism statable in advance, (iii) without breaking the regression
instruments. Shipping any of them would be squeezing the tuning split
with path churn. The shipped `edits.json` therefore contains only the
non-critical control group (§5), and the prediction recorded in it —
before final scoring — is an effect of exactly 0 on every instrument.

## 4. Trialled variants (all include the control rows; scored on round3_diag; adopted = 85.0%, 51/60, failures = the 9 of §1)

| Variant | Lever (kind) | round3_diag | Gained | Lost | Regressions (diag / r1 / r2) | Verdict |
|---|---|---|---|---|---|---|
| weto1 | 'We'+'To' suppression, additional β=1.0 (round-2 lever, dose escalation) | 85.0% (51/60) | none | none — failure set item-for-item identical | not run (identical on tuning split) | The round-2 doors are already shut; more dose does nothing. |
| the2 | 'The' (785) suppression β=2.0 (new opener) | 85.0% (51/60) | r3diag-021 | r3diag-059 | 88.75 (0 net) / 88.3 (−1) / **88.3 (−2: r2diag-055, 057)** | Net 0 with ±1 churn on the tuning split and net-negative regressions. 021 is a completed mul slip — its flip is path lottery, not mechanism; 059 (a correct compare) and two round2 items pay for it. Rejected. |
| dd2 | '$$' (14085) suppression β=2.0 (mid-output scaffold token — different in kind: gates verbosity throughout generation, not the first token) | 85.0% (51/60) | none | none — identical | **90.0 (+1: diag-058, zero lost)** / 90.0 (identical) / 91.7 (identical) | Does not beat the tuning split (gate i fails) and does not flip 040 — its $$ blocks survive. The single diagnostic gain is itself churn: adopted diag-058 fails on content (counts one day of purchases, not two), and the flip is a path change, not scaffold shortening. Recorded as a near-miss signal only. |
| dd4 | '$$' suppression β=4.0 (dose escalation of the above) | **83.3% (50/60)** | none | r3diag-023 | 90.0 (+1 diag-058) / 90.0 (identical) / 91.7 (identical) | Net-negative at higher dose; 040 still fails. Scaffold lever dead at both doses. |
| rb075 | Digit-dose rollback 0.75 (partial undo of round-1's +2.75 — tests whether the 3 compare inversions are dose-induced input-side distortion) | 86.7% (52/60) | r3diag-040 | none | **87.5 (−1: diag-009)** / 90.0 (0 net) / **88.3 (−2: r2diag-003, 007)** | The only zero-loss tuning-split gain — and it fails gate (iii) and gate (ii). No compare item flips at either rollback dose, so the dose-inversion hypothesis is falsified on this battery; 040's flip is a wording change in the same essay ("After 4 days:" for a longer phrasing) that happens to fit the cap — path-length lottery, not a mechanism. Regressions pay −3 items net. Rejected. |
| rb150 | Digit-dose rollback 1.5 | 86.7% (52/60) | r3diag-002, r3diag-040 | r3diag-004 | not run (churn signature already decisive on the tuning split) | ± churn in both directions: a subtraction slip flips right (002), a previously correct item re-opens a "We are given the expression" essay and truncates at "3" (004). Rollback weakens the digit-first grip round 1 bought; the flips are the lottery, in both directions. Rejected. |

Trial scalars changed: weto1 22,950; the2 22,838; dd2 22,782; rb075
31,120 (42 records each for the rollback trials) — all within the 0.1%
bound. (First dd2 attempt failed to build: the shell expanded `$$` to a
PID inside the trial script's double quotes. Recorded here, fixed by
single-quoting, re-run clean; the failed attempt scored nothing.)

What the trials jointly establish: every remaining round-3 failure is
either (a) decided wrong at the first digit on a path no bias in this
family can re-route without equal-and-opposite churn elsewhere
(055/057/058, 002, 020), (b) a completed-path content/procedure error
whose flips under any re-routing are symmetric lottery draws
(001/005/021 — cf. the2's +021/−059, rb150's +002/−004), or (c) the
single truncation 040, whose door is a multi-token name restatement —
there is no single row whose suppression claims it, and the two levers
that did flip it (rb075/rb150) flip it only as wording luck while
costing regression items. This is the same unreachable-mass verdict as
slice 42's zero yield on procedure/knowledge failures, now measured on
the loop's own third battery.

## 5. Non-critical group — `control-rows-predicted-inert` — edits N1–N11 + twins, NON-CRITICAL (the entire shipped patch)

Rows 151646–151656 (reserved special tokens this text model never
emits), each += −(2.0/133.66)·m̂_r3 in both stored copies
(`model.embed_tokens.weight` AND `lm_head.weight`) — identical
construction to the round-1/round-2 controls. Stated prediction, made
before final scoring (and recorded in `edits.json`): inert, effect
exactly 0, item-for-item identical to the adopted model everywhere.

## 6. Self-ablation (built with patch.py from the final edits.json, scored on round3_diag)

| Model | round3_diag | Reading |
|---|---|---|
| Adopted (input) | 85.0% (51/60) | fails: the 9 of §1 |
| **Full patch (control-only)** | **85.0% (51/60)** | failure set identical to adopted, item for item — as predicted |
| Minus-critical (`--exclude-critical`) | 85.0% (51/60) | identical — trivially: the critical group is empty, so this build is the full build; that identity IS the negative's claim (there is no critical group whose removal changes anything) |
| Minus-random (`--exclude-random-count 11 --random-seed 20261103`) | 85.0% (51/60) | identical — half the control records dropped at random, still inert |
| Minus-noncritical (`--exclude-noncritical`) | 85.0% (51/60) | identical — a byte-copy of the input model scores the same, closing the loop: the shipped directory differs from the adopted model only in rows that provably do nothing |

Scalars changed by the shipped patch: **21,142** (from
`patched-round3/patch_receipt.json`) — all in never-emitted
special-token rows; fraction 0.002813% of 751,632,384 (bound 0.1% =
751,632).

## 7. Regression checks (adopted baselines re-measured by me this round; all three reproduce the ledger exactly)

| Instrument | Adopted | Full patch | Churn |
|---|---|---|---|
| `diagnostic` (80 items) | 88.75% (71/80) | 88.75% (71/80) | +0 / −0, failure set identical |
| `round1_diag` (60 items) | 90.0% (54/60) | 90.0% (54/60) | +0 / −0, failure set identical |
| `round2_diag` (60 items) | 91.7% (55/60) | 91.7% (55/60) | +0 / −0, failure set identical |

## 8. What remains broken (unchanged by this round, by evidence)

- 3 comparison inversions with no positional consistency and (two of
  three) near-zero first-digit margins in the wrong direction — the
  comparison *content* is wrong, and rollback of the digit dose does
  not repair it (falsified at 0.75 and 1.5).
- 4 arithmetic slips on completed, often digit-first, paths.
- 1 operation-sign error ("sold" added) — procedure, unreachable by
  this family in rounds 2 and 3 alike.
- 1 cap truncation (040) entering through a multi-token name
  restatement; reachable only by wording luck that costs more
  elsewhere.

## 9. Predicted held-out effect (stated for the coordinator's scoring)

**Prediction: 0 points (held-out stays 87.5%).** The shipped patch is
control-only and reproduces the adopted model item-for-item on all 260
items of the four instruments I can see; there is no mechanism by which
it could move held-out. Cumulative gap closure stays at round 2's level:
7.0 of 19.5 points (35.9%).

## 10. Honest statement on round 4

No reachable mass remains for this patch family, and I do not believe a
round 4 within the family (sparse m̂-direction bias edits to embedding /
head rows) has anything to harvest: format mass is exhausted (one
truncation left, behind a multi-token name door), and the residual
8/9 failures are content/procedure errors whose every measured flip
under re-routing is matched by churn of the same size in the other
direction. A round 4 would need a different instrument altogether —
edits that touch computation (e.g. targeted MLP/attention surgery
informed by where comparison is actually computed), training, or a
larger token budget for the truncation class — none of which is this
loop's patch family. Under the loop's own plateau rule (round 2:
+2.0; round 3: 0), the evidenced recommendation from the teacher side
is: **stop the loop here.**
