# Qwen3-0.6B — G2 (framing) patch — EXPLANATION

Base: the chained G1 patch output. Diagnostic (chained base)
**19.17%** → after: **38.33%**. Dose: 8,192 stored scalars =
**0.00109%**.

## Diagnosis (diagnostic split, chained model's outputs)

The G1 patch already lifted G2 from 3.33 (pristine base) to
19.17. What remains:

- false_claim 11.9% and order_swap 40.5%: yes/no under framing.
  On chained hidden states, the pooled framed restricted argmax
  is only 0.44 (vs 0.73 for G1's plain compare): framing rotates
  the yes/no geometry. A G2-specific centroid simulates to
  0.86 at scale 0.2 (Euclidean 0.81).
- quoted_question 0/31: bare WRONG numbers — the first operand
  emitted directly (the G1 machinery strips the prose that used
  to surround the computation). Same unreachable class as G1's
  small_add: the answer is not at the readout position.
- distractor 0/5: name-echo prose frames ("Sam has **2 boats**.")
  — the gold is present but framed; name tokens vary per item,
  no stable row set exists. Not targeted.
- not_category 60%: content choices on an open word set. Not
  a readout failure. Not targeted.

## Components

- **framed_yesno_readout** (E1–E2, critical): E7 centroid
  direction+bias on 'Yes'/'No' rows, class means from the
  false_claim + order_swap diagnostic items of the CHAINED
  model, scale 0.06.
- **controls** (E3–E4, non-critical): matched controls on
  never-emitted special rows.

## The interference finding (why scale 0.06, not 0.15)

Candidate 1 (scale 0.15 + an EOS refresh on G2 continuation
geometry) scored G2 40.83 — but G1 diagnostic retention fell
47.50 → 25.83 (yes_no_compare 91.89 → 37.84, copy 100 → 80,
plus empty outputs from stacked EOS pressure: the two EOS
deltas add). The framed centroid and the plain-compare
centroid share the same two rows and pull them in different
directions; one linear readout cannot hold both geometries
at full strength. Candidate 2 (this patch, scale 0.06, no EOS
refresh) is the balance point: G2 38.33 with G1 diagnostic
retention 38.33 (copy/seq/last_word fully retained;
yes_no_compare 62.16 — the residual interference, recorded
as this grade's boundary fact).

## Result by category (diagnostic)

distractor 0→0, false_claim 11.90→47.62, not_category 60→60,
order_swap 40.54→62.16, quoted_question 0→0.

## E4 self-check (diagnostic)

Full 38.33 / minus-critical **19.17** (= chained base exactly)
/ minus-random (seed 41) **16.67**. The effect follows the
critical set.
