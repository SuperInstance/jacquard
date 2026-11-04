# Qwen3-0.6B — G3 (readout) patch — EXPLANATION

Base: the chained G2 patch output. Diagnostic (chained base)
**39.17%** → after: **41.67%**. Dose: 28,672 stored scalars =
**0.00381%**.

## Diagnosis (diagnostic split, chained model)

Per label set, probed on chained hidden states:

- vowel_start (18): Euclidean centroid **1.00**; simulated
  row patch reaches 1.00 at scale 0.15. Fully separated.
- plural_check (5): centroid 1.00, sim 1.00 at any scale.
- sentiment (5): already 100% — no patch needed or applied.
- contains_letter (40) + case_check (30), the grade's yes/no
  mass: pooled centroid **0.54**, BELOW the 0.70 majority rate
  ('no' is 49/70). The letter-presence/case readout does not
  separate in this model — a centroid patch would install a
  worse-than-constant classifier. Declared not patchable by
  family 1; no component targets it (the profile result for
  G3's largest categories).
- length_compare (22): open word set, 50% at chained base —
  content choice, not a label readout. Not targeted.

## Components

- **vowel_readout** (E1–E2, critical): centroid direction+bias
  on the first-token rows of 'vowel' ('v', 85) and 'consonant'
  ('con', 443), scale 0.1, class means from vowel_start items.
- **plural_readout** (E3–E4, critical): same form on
  'singular'/'plural' rows, scale 0.05.
- **label_continuation** (E5–E7, critical): 'owel', 'son',
  'ant' rows += +25 logits along the continuation-mean
  direction — added in candidate 2 after candidate 1's failure
  (below).
- **controls** (E8–E14, non-critical): matched controls.

## What actually happened (the grade's boundary finding)

Candidate 1 (no continuation boosts): plural_check 40→100 as
predicted, but vowel_start fell 44.44→33.33 — outputs were
'con' and 'v': the first-token readout fired CORRECTLY on
every item, then the inherited EOS pressure (G1's format_stop)
stopped the model mid-word. Candidate 2's continuation boosts
fixed the truncation but cross-wired the completion:
consonant items now complete as **'conowel'** — a context-free
row boost cannot prefer 'son' after 'con' over 'owel' after
'con'; that preference is context-conditional, which a single
row bias does not express. Final vowel_start: 44.44 (unchanged
in score, changed in kind: first-token readout is installed
and perfect; word completion is the unseparated step).
Net grade effect: +2.50, carried by plural_check.

Retention cost (diagnostic): G1 38.33→35.00, G2 38.33→32.50
after this patch — the 'v'/'con' rows are also input embeddings
for prompt words, and the drift is recorded, not hidden.

## E4 self-check (diagnostic)

Full 41.67 / minus-critical **39.17** (= chained base exactly)
/ minus-random (seed 41) **40.00**. Holds, with one honest
qualification: minus-random retains part of the plural gain
(60 vs 40 base, n=5) — random same-norm deltas on the
singular/plural rows bias the pair by chance at this n.
