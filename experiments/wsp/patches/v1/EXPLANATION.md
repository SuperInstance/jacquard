# EXPLANATION — Jacquard Phase 15, slice 41 (E1 + E4), patcher v1

Student: Qwen/Qwen3-0.6B (bf16, tied embeddings, 28 layers, hidden 1024,
751,632,384 parameters). Patch artefacts: `patch.py` + `edits.json` in this
directory. All numbers below were produced with the fixed instrument
(`score_diag.py`, diagnostic split, greedy, 96-token cap, last-number
extraction) run against model directories built by `patch.py` itself.

**Result: diagnostic 63/80 = 78.8% (base) → 72/80 = 90.0% (patched).**
Receipt: 44 edit records (22 logical edits × 2 stored copies, see §4),
**43,028 scalars changed = 0.005725%** of parameters (bound: 751,632 = 0.1%).

---

## 1. Diagnosis — what actually fails in the base model

Base diagnostic failures: 17 of 80. Classified from the scored raw outputs
(reproduced exactly by the fixed harness; identical to the coordinator's
baseline per-category numbers):

| Failure class | Count | Items | Description |
|---|---|---|---|
| Truncation at the 96-token cap | 6 | diag-003, 005, 007, 009, 066, 074 | Model writes a correct, verbose LaTeX/markdown worked solution ("We are given the expression… ### Step 1… $$…") that runs out of tokens mid-final-step; the extractor reads a partial number ("…= 8", "…= 1", "**Answer: 58"). The arithmetic on the page is right; the answer never lands. |
| Last-number extraction vs. sentence frame | 3 | diag-072, 073, 080 | Model states the *correct* comparison in a sentence "The number 8279 is larger than 1876." — the last number in the text is the *smaller* one, so the scorer reads it as the answer. Content right, record wrong. |
| Wrong operation | 2 | diag-006, 010 | "stocked X, sold Y, delivery Z" word problems where *sold* is added instead of subtracted (391 + 170 + 333 = 894). |
| Arithmetic slip | 5 | diag-004, 024, 025, 027, 070 | Completed outputs with a wrong value (302−259+192 = 135; 51×37 = 1907; 83×47 = 3941; 74×85 = 6370; 4.00/8 = 1.00). |
| Wrong comparison choice | 1 | diag-078 | Model picks the smaller number as greater (2459 over 6065). |

**Headline: 9 of 17 failures (53%) are format/completion failures, not
arithmetic failures.** The model's dominant failure mode is that it ignores
"Answer with just the number" and writes an essay. Two probes sharpened this:

- *First-token probe.* For direct prompts the model's top first token is
  already a digit (rank 1); for verbose prompts the best digit sits at rank
  2–17, typically 3–7 logits behind openers like "We"/"The"/"To". The
  capability to answer directly is present; the style prior outvotes it.
- *Compare probe.* At the answer-initiation position the model's best digit
  is the first digit of the *correct* larger number on 8 of 10 compare items
  (including items its verbalised answer later got wrong or buried). Its
  latent comparison is better than its verbalised one.

## 2. Group `digit-first-answer-bias` — edits C1–C10 (+ twins C1T–C10T), CRITICAL

**Which weights.** Rows 15–24 of the (tied) embedding matrix — the rows for
the single-digit tokens '0'…'9'. Qwen3 tokenises numbers digit-by-digit
(verified: "1387" → tokens 16,18,23,22), so these ten rows are the entire
output vocabulary of numeric answers, and simultaneously the input
embeddings of every digit the model reads.

**What they compute / mechanism claim.** A token row is the token's logit
template: logit = h·row at the final hidden state h. The measured fact this
edit exploits: final hidden states at the answer-initiation position share
a dominant common direction. Averaging h over the 80 diagnostic prompts
gives a mean direction m̂ (unit norm) with h·m̂ = 133.5 on average, and —
critically — a narrow range (118–144): hidden states are ~90% aligned with
this shared component. Adding the *same* vector α·m̂ to a row therefore adds
an almost context-independent constant α·(h·m̂) to that token's logit
wherever the model is about to answer — an authored bias term, built from
the model's own activation geometry. With α = 5/133 the digit logits gain
≈ +5 at answer initiation.

Because the *identical* vector is added to all ten digit rows, digit-vs-digit
logit differences are untouched at the output side: the edit does not tell
the model *which* digit, it tells it *a digit, now*. On the input side
(tied embeddings) every digit token read carries the same additive offset —
a constant "digit channel" shift that preserves digit identity (differences
between digit embeddings are unchanged).

**Why these edits / evidence.** +5 is calibrated to the measured first-token
gap (3–7 logits between the verbose opener and the best digit). Effect:
the model flips from essay style to compact arithmetic style — e.g.
diag-001 becomes "7014 + 673 − 6300 ⏎ 7014 + 673 = 7687 ⏎ 7687 − 6300 = 1387
⏎ **Answer: 1387**" — which completes well inside the token cap, keeps a
short scratchpad (so multi-step arithmetic still has working room), and ends
with the answer as the last number. This single group (measured alone):
addsub_chain 30%→70%, unit_price 80%→100%, overall 78.8%→83.8% (67/80).
Larger boosts (+8, +11) were tried and *hurt*: the tied input-side offset
grows and begins flipping near-tie digit decisions inside multiplications
(mul_2x2 fell to 4–5/10) — the +5 point is a measured optimum on a plateau
(+4/+5/+6 all give the same addsub/unit gains).

**Provenance, honestly stated.** m̂ is a measured activation statistic of the
base model on the diagnostic prompts (a forward-pass probe — no gradients,
no optimiser, no fitted parameters anywhere in this process). α was selected
by iterating on the diagnostic split, as the protocol allows. The bf16-rounded
delta values are stored explicitly in `edits.json`.

## 3. Group `compare-frame-break` — edit C11 (+ twin C11T), CRITICAL

**Which weights.** Row 1091, the token ' than', scaled ×0.75.

**Mechanism claim.** Under the digit bias, compare items come out as
"8279 is larger than 1876." — still failing, because the scorer reads the
last number. Measured logits explain why the obvious fixes fail: immediately
after the model emits the (correct) larger number, the continuation ' is'
sits at 27.25 while <|im_end|> is at 7.84 — the canned frame "X is larger
than Y" outvotes stopping by ~19 logits, so no survivable EOS boost can end
the answer at the number (EOS boosts of +3…+13 via the same direction were
tried; they truncated healthy solutions elsewhere and never fixed compare).
But after a *complete* sentence the model's <|im_end|> is the top token
(29.38, measured): it stops happily — the problem is purely that the frame's
bridge token ' than' drags the smaller number into last position. Scaling
the ' than' row ×0.75 cuts its logit by a quarter wherever it is proposed;
at the frame position that is enough for '.' to win instead. Outputs become
"8279 is larger." / "9784 is greater." — the model's own (mostly correct)
comparison, stated, stopped, and with the answer as the last number.

**Evidence.** Adding this one row to the digit group: compare 30%→80%
(3/10→8/10), overall 83.8%→90.0%. The scale is on a plateau (×0.4, ×0.5,
×0.65, ×0.75 all give identical diagnostic results and identical failure
sets); ×0.75 was chosen as the weakest version with the full effect, to
minimise collateral (see §5). The two remaining compare failures
(diag-075 "6738 is greater", diag-078 "2459 is greater") are genuine
comparison-content errors — the model now honestly reports a wrong
comparison instead of a correct one in a broken frame. No edit in this
patch claims to fix comparison *content*.

Variants tried and rejected on evidence: scaling ' larger'/' greater' rows
(no effect — the model routes through other surface forms: "is much
**larger**", ">"), scaling ' is' ×0.6 (compare 4/10, prose cost 3× higher),
boosting '.' or '\n\n' rows (no compare gain; broke word_2step/pct items).

## 4. The twin-copy requirement (checkpoint structure)

The checkpoint stores the tied embedding **twice** — `model.embed_tokens.weight`
and `lm_head.weight`, byte-identical in the base — and the config ties them on
load. A patch that edits only one stored copy silently unties the head:
transformers then refuses to tie and the output head stays unpatched.
Verified experimentally: the embed-only version of this exact patch scores
64/80 (worse than the tied patch's 72/80, better than nothing — the
input-side half of the mechanism still acts). Every logical edit is therefore
emitted in `edits.json` as a twin pair (ids `C1`/`C1T`, …), one per stored
copy, and the receipt counts both copies (43,028 scalars total).

## 5. Group `control-rows-predicted-inert` — edits N1–N11 (+ twins), NOT critical

**Which weights.** Rows 151646–151656: reserved special tokens
(<|object_ref_start|>, <|box_start|>, <|vision_start|>, <|image_pad|>, …) —
vision/object-reference tokens this text-only model never emits in these
batteries (measured base logits −4.4…−7.2 against top logits of ~27; after
the +5 delta they remain ~20 logits below contention). Each receives the
*identical* delta vector as the digit rows.

**Role.** These are a deliberate, honestly-labelled control group: same
tensor, same selector kind, same op, same values, same count as the critical
set — differing only in which tokens they touch. Their stated prediction is
inertness. Earlier candidates for a "real but minor" non-critical group
(symbol rows '+', '=', '%', … at +1.0 and even +0.25 along m̂) were measured
*not* inert — they flip near-tie items elsewhere (mul_2x2/pct/unit_price
items moved) — so they were dropped rather than mislabelled; the control
rows are the non-critical set whose inertness is verified, not assumed.

## 6. The critical prediction (E4) — and my own ablation measurements

**Prediction.** Ablating the full critical set (C1–C11 + twins) kills the
effect: diagnostic returns to base level. Ablating an equal count of
non-critical edits (N1–N11 + twins) does not: diagnostic stays at the
patched level.

Measured with `patch.py` + the fixed scorer before declaring FINAL:

| Model | Diagnostic | Per-category highlights |
|---|---|---|
| Base | 63/80 = 78.8% | addsub 30%, compare 50%, unit_price 80% |
| Full patch | **72/80 = 90.0%** | addsub 70%, compare 80%, unit_price 100% |
| − critical (controls only) | 63/80 = 78.8% | per-category *identical to base*, failure set identical to base |
| − non-critical (core only) | 72/80 = 90.0% | per-category and failure set identical to full patch |

## 7. What remains broken, and collateral

Remaining diagnostic failures under the full patch (8): arithmetic slips
diag-004, 024, 025, 027 (the model's raw computation, untouched by this
patch and — I claim — not addressable by any comparably sparse authored edit
I could find); wrong operation diag-010 (sold still added); truncation
diag-006 (this prompt's verbose prior is too strong for the +5 bias — its
first-digit gap was among the largest measured — and it now computes the
operations *correctly* but still runs out of tokens in essay style);
comparison-content errors diag-075, 078.

Collateral probe (self-authored harbour paragraph, deliberately dense in
"than/larger/greater" phrasing — a worst-case-ish text I wrote for this
check, not battery material): mean NLL 3.7295 (base) → 3.7643 (patched),
Δ ≈ +0.035, attributable to the ' than' scaling. The digit and control rows
contribute negligibly (reserved tokens never surface; digit logits in prose
positions remain far from winning). No category that was at 100% in the base
regressed on the diagnostic split.

## 8. Predicted held-out effect

Diagnostic gain is +11.25 points, but the diagnostic split was the tuning
split, so I discount it. The two mechanisms are template-level, not
item-level (essay-style truncation and the compare sentence frame are
properties of the prompt templates, and validation aggregates show the same
two categories failing there: addsub_chain 48%, compare 52% at an 83.5%
overall baseline). **Predicted held-out effect: ≈ +8 points (range +5…+11)**
— above the ~5-point noise band for n=200, driven mostly by addsub_chain
and compare recovering toward their content-correct levels, with the
categories already at 100% (div, mul_2x1, pct, unit_price) expected to hold.
