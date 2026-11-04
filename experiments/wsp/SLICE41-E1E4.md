# Slice 41 — E1 (replication) + E4 (explanation falsification)

Student: Qwen/Qwen3-0.6B (751,632,384 params, tied embeddings).
Instrument: the reviewed + fixed battery harness (BATTERIES.md;
review findings B1-B4/N1-N5 fixed before any patch work — the
first baseline measured with the unfixed harness is superseded).
All scores below are coordinator-run with score.py on the Thor;
the patcher saw only the diagnostic split and validation
aggregates.

## Baselines (fixed instrument)

| split | accuracy | weakest categories |
|---|---|---|
| diagnostic (80) | 78.8% | addsub_chain 30%, compare 50%, mul_2x2 70% |
| validation (200) | 83.5% | addsub_chain 48%, compare 52% |
| heldout (200) | 80.5% | addsub_chain 48%, mul_2x2 44%, unit_price 72% |
| forget_instr (100) | 81% | ends_with 47%, word_count_range 38% |
| forget_fact (100) | 85% | misc 56%, solar_system 53% |
| forget_prose (24) | NLL 4.0688 | — |

Diagnosis (patcher, from diagnostic raw outputs; coordinator
concurs): 9 of 17 diagnostic failures are format/completion —
6 worked solutions truncating at the 96-token cap with the
arithmetic on the page correct, 3 correct comparisons buried
by the sentence frame ("The number 8279 is larger than 1876"
— the extractor reads the last number). 8 are content
(5 arithmetic slips, 2 wrong-operation, 1 wrong comparison).

## E1 — the patch (patches/v1/)

22 logical edits (44 records — the checkpoint stores the tied
embedding twice and both copies must be edited; editing one
silently unties the head and scored 64/80, a trap the patcher
found and documented). 43,028 scalars = 0.0057% of parameters.

- Digit-first bias (C1-C10, critical): add alpha * mean-hidden-
  direction to the ten digit rows of the tied embedding
  (alpha = 5/133, ~= +5 logits at answer initiation). Exploits
  a measured fact: final hidden states at answer initiation
  are ~90% aligned with a shared direction (h.m = 133.5,
  range 118-144), so one authored vector is a near-constant
  logit bias toward starting with a digit — flipping the model
  from essay style to compact arithmetic that lands inside
  the token cap.
- Compare-frame break (C11, critical): scale the ' than'
  token row x0.75, so correct comparisons end with the larger
  number ("8279 is larger.") instead of dragging the smaller
  one last.
- Controls (N1-N11, non-critical): the identical delta applied
  to 11 never-emitted special-token rows — a matched-count,
  matched-form ablation control, labelled as such in advance.

## E1 — results (coordinator-scored)

| split | base | patched | delta |
|---|---|---|---|
| validation | 83.5% | 91.5% | +8.0 |
| heldout | 80.5% | 85.0% | +4.5 (14 gains / 5 losses) |
| forget_instr | 81% | 81% | 0 (1 gain / 1 loss — churn, not damage) |
| forget_fact | 85% | 85% | 0 (item-identical) |
| forget_prose NLL | 4.0688 | 4.0739 | +0.005 (negligible) |

Heldout per-category: addsub_chain 48% -> 84% (the truncation
class, transferring across template sets as the mechanism
predicts), word_2step 84% -> 92%, compare 100% -> 100%;
small regressions inside per-category noise (unit_price
72% -> 64%, pct_of 100% -> 96%; n=25 per category).

Reading, stated plainly: the effect is real and mechanism-
consistent — same direction on validation (+8.0) and heldout
(+4.5), concentrated in the category the mechanism targets,
with zero measured forgetting. It is also MODEST: +4.5 on
n=200 is ~1.6 sigma, and the patcher's predicted +8
(range +5..+11) overshot — tuning-split optimism, recorded.
Nothing here resembles the source claim's 6x: that claim was
about benchmark capability scores; this battery's dominant
failure was behavioural (the model's latent arithmetic was
mostly intact — its first-token digit was already the correct
answer's first digit on 8/10 probed compare items). What E1
shows at this scale: a sparse authored patch (0.0057% of
weights, no gradients) can reliably fix a diagnosed
behavioural failure class in a small model, generalise
across surface forms, and leave everything else measurably
untouched.

## E4 — is it engineering (coordinator ablation, seed 41)

Variants materialised independently by the coordinator from
patch.py + edits.json on the pristine base:

| variant | heldout | validation | forget_prose NLL |
|---|---|---|---|
| full patch | 85.0% | 91.5% | 4.0739 |
| minus critical (controls only) | 80.5% | 83.5% | 4.0688 |
| minus random 22 (core only) | 85.0% | 91.5% | 4.0739 |
| base | 80.5% | 83.5% | 4.0688 |

The explanation's prediction holds EXACTLY on held-out data:
ablate the claimed-critical edits and the effect vanishes to
the base score on every measure; ablate an equal count of
non-critical edits and the effect persists unchanged; restore
(the full variant) and it returns. The independently rebuilt
"full" variant reproduces the patcher's own patched model
scores to the item — the artefacts are the patch. E4 verdict:
the patch is engineering, not numerology — its author's
mechanism claims are causally correct at the granularity
claimed. One honest boundary: the explanation is at the level
of logit geometry (which rows, what bias), not circuit-level
(which heads/MLPs compute the comparison) — the ablation
supports the claims as stated, and the claims were stated at
exactly the level the evidence supports.
