# EXPLANATION — Jacquard Phase 15, E5 stage 2 (T2: date/interval arithmetic)

Student: Qwen/Qwen3-0.6B (bf16, tied embeddings, 28 layers, hidden 1024,
751,632,384 parameters). **Base for this stage is the stage-1 patched model**
(`model-in/`); this patch composes on top of it and does not touch stage 1's
edits. Artefacts: `patch.py` + `edits.json` in this directory, built model in
`patched-stage2/`. All scores from the fixed instrument (`score.py`, greedy,
96-token cap, last-number extraction) run against model directories built by
`patch.py` itself. No training, no gradients, no optimiser anywhere: the only
measurements are forward-pass probes on the diagnostic split, exactly as in
stage 1.

**Result: T2 diagnostic 11/60 = 18.3% (stage-1 model) → 16/60 = 26.7%
(stage-2 model). T1 diagnostic regression check: 90.0% → 90.0% (72/80,
per-category identical).** Receipt: 32 edit records (16 logical edits × 2
stored copies), **31,450 scalars changed = 0.00418%** of parameters
(bound: 751,632 = 0.1%).

This is a **small positive, honestly bounded**: unlike T1, most T2 failures
are not format failures. §7 states what this patch provably cannot reach.

---

## 1. Diagnosis — what the stage-1 model actually does with a date prompt

All 60 diagnostic items classified from the stage-1 model's raw outputs
(`diag_for_patcher.jsonl`); 49 misses:

| Failure class | Count | Where | Description |
|---|---|---|---|
| No mod-7 reduction | 9 | weekday_offset | Model adds start number + offset correctly (5+10=15, 6+4=10, 3+15=18), then answers the unreduced sum, maps it wrongly (16→Monday), or truncates while reciting the mapping. Only 1/12 correct (the one item where it spontaneously wrote "30 mod 7 = 2"). |
| Misread question semantics | 6 | add_days_count ("days left") | "How many days are left in the month after 17 June" is parsed as "days in the month *after* June" → answers the next month's length (31) or a hallucinated day number. Gold is month_length − day. Zero of 6 correct under any style variant tried. |
| Canned / attractor answers | 9 | days_between 5, month_span 4 | Cross-month day counts collapse to attractors: "120 days" for three different date pairs, "100天"; month_span collapses to "2 months" or "12 months" regardless of span. |
| CJK date restatement | 3 | days_between | Prompt echoed back as a Chinese date sentence (2025年8月22日到…), dates mangled (21 Feb → "2月1日"), canned count follows. (Suppressing the Chinese path reroutes one item to the Korean path — same failure in another language; see §4.) |
| Essay / enumeration truncation | ~13 | all except weeks_days | "To find the number of days between…" essays, day-by-day enumerations (60–87 steps), and month-listing essays run into the 96-token cap mid-procedure; extractor reads a partial number. |
| Wrong direct date arithmetic | 5 | add_days_count ("move forward") | When the model does answer directly it adds whole months wrongly: 6 Feb + 60 d → "6 August"; 24 Feb + 5 d → "29 February" (Feb 2025 has 28 days); 25 Mar + 62 d → "25 April". |
| ÷7 content errors at magnitude | 5 | weeks_days | Small divisions are right (63→9, 46→6 r4). At 3 digits the divisor itself slips: 105→35 weeks and 104 leftover computed as "28 × 3 = 84" (÷3 instead of ÷7); 97→14 (rounds 13.86 up, writes "14 × 7 = 98" without noticing); 34 "whole weeks"→5 (rounded) while the same model's remainder phrasing for 34 gives 4 r6. Category still best at 7/12. |
| Correct | 11 | — | Mostly same-month subtraction, small ÷7, one mod-7 success. |

**Headline contrast with T1:** in T1, 53% of failures were format/completion
and the arithmetic underneath was right. Here the procedure itself is the
failure for the majority: no mod-7 wrap, no reliable month-length use in
computation, ÷7 unreliable at magnitude, one systematic question misreading.

Two probes sharpened what *is* present:

- *Continuation probe (teacher-forced diagnostic prefixes).* Given a correct
  decomposition written out, the model's next-step arithmetic is strong:
  "June has 30 days. 30 − 17 =" → top token '1' (of 13) at logit 28.9 vs 19.1
  for the runner-up; "3 + 25 =" → '2' (28); "112 / 7 =" → '1'; "105 / 7 =" →
  '1'. The primitives fire when the decomposition is on the page; the model
  does not spontaneously *produce* the decomposition.
- *Latent first-token probe.* The gold answer's first digit is the argmax
  digit at answer initiation on only 11/60 items (the argmax is usually the
  echoed date digit '2'/'1'). There is no latent direct-answer capability to
  unmask, and extra digit bias confirms it (§5).

## 2. What this patch does — failure-path suppression (the only lever that moved T2)

Stage 1's lever (digit bias along the mean hidden direction m̂) does not
transfer: §5 records that strengthening it buys a little T2 and costs T1.
What *did* move T2, at zero T1 cost, is the symmetric operation on the
*failure paths themselves*: negative authored logit biases, built from the
same activation geometry, on the specific tokens that open the failing
generation templates.

Mechanism (same as stage 1, sign flipped): final hidden states at answer
initiation share a dominant direction; measured on the 60 T2 diagnostic
prompts of the stage-1 model, h·m̂ = 132.0 mean (range 123.6–141.8;
cos(m̂_T2, m̂_T1) = 0.944). Adding δ = (c/132.0)·m̂ to a token's tied
embedding row therefore subtracts ≈ c from that token's logit wherever the
model is about to generate — an authored, context-light bias. bf16-rounded
delta values are stored explicitly in `edits.json`; provenance is a
forward-pass activation statistic of the base model on diagnostic prompts,
no fitted parameters.

### Group `essay-opener-suppression` — edits S1–S6 (+ twins), CRITICAL

Rows: 'To' (1249, −8), 'We' (1654, −5), 'Starting' (24617, −8), 'Given'
(22043, −4), 'Since' (12549, −4), 'From' (3830, −5).

These are the first tokens of the truncating templates measured in §1:
"**To** find the number of days between…", "**We** are given that…",
"**Starting** on 6 February… - 6 February → 7 February →…" (the enumeration),
"**From** **12 August 2025** to…" (followed by a day listing). Suppressing the
opener does not teach any procedure; it denies the model its longest,
cap-busting openings, so a larger share of generations take a shorter path
that either completes a procedure it does know or lands a direct answer.
Measured effect of the full patch per category is in §6; the flips include
genuine completions (t2diag-018: "28 mod 7 = 0, so it's al[so Wednesday]" —
the mod-7 procedure the base model owns but used to bury; t2diag-017:
"Thursday + 4 days = Monday (1)") and two template-luck wins (month_span
items whose canned "2 months" happened to be gold — recorded as luck, not
capability).

### Group `cjk-restatement-suppression` — edits S7–S8 (+ twins), CRITICAL

Rows: '年' (7948, −10), '년' (126216, −10) — the year tokens that open the
Chinese and Korean date-restatement paths (§1). With the Chinese token
suppressed alone, t2diag-003 rerouted to Korean and produced the same canned
120; both are therefore suppressed. Effect: t2diag-009 flips to a correct
English one-liner ("2025 February 21 to 26 is 5 days"); the other two items
reroute to English canned answers and still fail — the attractor (§1) is
deeper than the language path.

### The twin-copy requirement (inherited from stage 1)

The checkpoint stores the tied embedding twice (`model.embed_tokens.weight`
and `lm_head.weight`); every logical edit is emitted as a twin pair or the
head silently stays unpatched. The receipt counts both copies.

## 3. Group `control-rows-predicted-inert` — edits N1–N8 (+ twins), NOT critical

Rows 151646–151653 (reserved special tokens this text-only model never emits
in these batteries), each given the identical delta vector as S1 — same
tensor, selector kind, op, values and count as the critical set, differing
only in which tokens they touch. Stated prediction: inert.

## 4. The critical prediction (E4) — and my own ablation measurements

**Prediction.** Ablating the full critical set (S1–S8 + twins) kills the
effect: T2 diagnostic returns to the stage-1 model's 18.3%. Ablating an equal
count of non-critical edits (N1–N8 + twins) does not: T2 stays at 26.7%.
T1 stays at 90.0% in all variants.

Measured with `patch.py` + the fixed scorer before declaring FINAL:

| Model | T2 diagnostic | T1 diagnostic |
|---|---|---|
| Stage-1 model (this stage's base) | 11/60 = 18.3% | 72/80 = 90.0% |
| Full stage-2 patch | **16/60 = 26.7%** | **72/80 = 90.0%** |
| − critical (controls only) | 11/60 = 18.3% (per-category identical to base) | 72/80 = 90.0% |
| − non-critical (core only) | 16/60 = 26.7% (identical to full) | 72/80 = 90.0% |

Per-category, full patch vs base: weekday_offset 1/12→4/12,
days_between 1/12→2/12, month_span 1/12→2/12, add_days_count 1/12→1/12,
weeks_days 7/12→7/12. Flips: +6 (t2diag-009, 017, 018, 019, 049, 059),
−1 (t2diag-054, whose stage-1 truncated essay happened to end on the gold
number; the shorter path answers the "12 months" attractor).

## 5. Variants tried and rejected on evidence

- **More digit bias** (stage-1 lever, +3 → total ≈ +8 along m̂_T2): T2 25.0%
  but T1 fell 90.0%→85.0% (mul_2x2 7/10→4/10 — the tied input-side offset
  flipping near-tie digit decisions, the failure stage 1 documented at this
  strength). At +1.5 extra: T2 26.7%, T1 87.5%. Any digit strengthening trades
  stage-1 gains for stage-2 gains; rejected — the brief is composition
  without giving back T1.
- **Suppressing ' corresponds'** (−6) and **boosting ' mod'** (+3): T2
  unchanged at 26.7% in total (composition shifted), no weekday gain beyond
  the base suppression set. The mod-7 failure is not a missing 'mod' token;
  when the model writes the sum it does not reach for the reduction step at
  all. Dropped.
- **Suppressing ' has'** (−6, against the "2025 has 12 months" canned frame):
  month_span got *worse* (2/12→1/12). Dropped.
- **Suppressing ' can'** (−6, against the "can be split into" template echo in
  weeks_days): outputs unchanged in substance; the rounding/divisor errors
  are in the content, not the template. Dropped.
- **Stronger suppression set** (To −8, We −5, Starting −8, From −5, both CJK
  tokens): identical totals (26.7% / 90.0%) — the shipped values; the effect
  is on a plateau, so the set is not finely tuned to the diagnostic items.

## 6. What remains broken, and why I claim it is not sparse-patch-addressable

44 of 60 items still fail. The residual classes are *content* failures, and
the evidence that authored logit-bias edits cannot reach them is direct:
(i) the latent probe shows the correct answers are not computed anywhere a
bias could surface them (gold first digit argmax on 11/60); (ii) every
template-level rerouting tried converges to the same plateau (~27%) with the
same residual set; (iii) the residual errors are wrong *facts-in-computation*
(February has 29 days; ÷7 with divisor 3; month lengths never subtracted)
and a wrong *parse* (days-left misreading, 0/6 under every variant) — none of
these is a competition between surface forms that a constant logit offset
can arbitrate. The continuation probe (§1) shows the arithmetic primitives
exist behind a decomposition the model will not write; making a model
*generate a procedure it does not generate* is a capability gap, not a style
prior, and at 0.004% of parameters an authored patch is the wrong tool for
it. I record this as the stage's main finding: **E5's chain reaches its
authored-patch ceiling quickly — stage 1 harvested a format failure;
stage 2's target is a procedure failure, and the same instrument buys
+8.3 points of truncation relief and no procedure.**

## 7. Predicted held-out effect

Diagnostic gain is +8.3 points (n=60, tuning split). The mechanism is
template-level (the same prompt templates generate the held-out split;
truncation relief and opener suppression are properties of the templates,
not of the items), which argues for transfer; but two of the six gained
items are template-luck, and the diagnostic was the selection split.
**Predicted T2 held-out effect: ≈ +4 points (range 0…+8)** over the stage-1
model's held-out baseline — inside-to-near the ±7-point noise band at
n=120, i.e. quite possibly indistinguishable from zero. T1 held-out should
be unaffected (T1 diagnostic and per-category scores are bit-identical in
behaviour to the stage-1 model under every variant measured).
