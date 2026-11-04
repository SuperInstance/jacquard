# R4 Round 1 — EXPLANATION (patcher)

Student: fresh Qwen3-0.6B (`~/wsp-exp/models/Qwen3-0.6B`, read-only),
fixed prompt in `experiments/wsp2/r4/score_student.py`, greedy,
first-label extraction. All geometry, directions and calibration
derived from the **diagnostic split only** (120 items). The
held-out split was never read, listed, or scored by this patcher;
validation was seen only as the builder's published aggregates
(student validation 36.7%: calm 20 / alarmed 90 / stampede 0).

## Label rows

- `' calm'` = token **19300**, `' alarmed'` = token **81040** —
  single tokens. `' stampede'` is two tokens: `' stamp'` **21206**
  + `'ede'` 15326; the first-token readout row for stampede is
  therefore 21206. The two stored copies
  (`model.embed_tokens.weight`, `lm_head.weight`) are
  byte-identical in the base file (verified) and receive
  identical edits. Verified after build: exactly these two
  tensors differ from base, exactly rows {19300, 81040, 21206}
  in each, row deltas match intent at cos = 0.999998 (bf16
  rounding), copies still equal.

## First-token geometry findings (probe.py / probe.npz, base model)

- Base 3-label argmax is **constant**: alarmed wins on all 120
  diagnostic items. Mean first-token logits by gold class —
  calm items [12.05, 19.73, 6.56], alarmed [11.47, 20.63, 5.54],
  stampede [11.07, 20.61, 5.58] (calm/alarmed/stampede order).
  The alarmed row carries a ~+8..+15 logit prior over the other
  rows for *every* input; the stampede row is last for every
  class. The generated-output baseline (30.0%: calm 0, alarmed
  90, stampede 0) is this same attractor seen through sampling
  of the full vocabulary.
- The classes **are** strongly separated in the final hidden
  state, in the Euclidean/cosine sense, not the raw dot-product
  sense: nearest-centroid on diagnostic hidden states =
  **88.3%** (calm 77.5 / alarmed 97.5 / stampede 90.0), cosine
  centroid 89.2%, while centroid dot-product = 33.3%. Reason
  (same as E7): `||mu|| = 184.39` dwarfs the class deviations
  (`||mu_calm−mu|| = 6.25`, `||mu_alarmed−mu|| = 5.85`,
  `||mu_stampede−mu|| = 6.85`; pairwise cos of deviations
  −0.36 / −0.61 / −0.53). A row edit changes logits by
  `h·Delta_c` — a bias-free linear functional — so the
  `−||mu_c||²` term of the centroid classifier is emulated by
  a component along the global mean direction m-hat:
  `h·m-hat = 184.39 ± 2.56` is near-constant, so
  `gamma_c·m-hat` acts as a per-class bias.

## Diagnosis: what the base answer tracks vs ignores

Feature table over diagnostic transcripts (substring lexicon
counts exactly as the incumbent computes them, trailing-30 s
density, cascade heat, construction parameters):

- The base prediction has **zero variance** (all-alarmed
  argmax), so it tracks no per-item feature at all. Its
  alarmed *margin* correlates only weakly with the signals
  present (cascade heat r=+0.40, genuineness r=+0.47, alarm
  hits r=+0.16).
- The features that *define* the gold classes are present in
  the transcripts and in the hidden states (centroid stampede
  recall 90%) but invisible to the readout: corroborator
  count correlates r=+0.95 with gold stampede, distinct
  authors +0.83, density +0.74, word count +0.70.
- Alarm-word density **anti-correlates** with genuineness
  (r=−0.23): calm rooms carry *more* distinct alarm hits on
  average (1.48/item) than alarmed (0.60) or stampede (0.97)
  rooms — the boundary calm subtypes (negation, fiction,
  drill, polysemy) are lexicon-rich by construction. Any
  readout keyed to lexicon density, including the incumbent
  dial's, is structurally wrong here; the base student's
  constant "alarmed" is not even that — it is a row prior.

## The input-side coupling (measured, larger than E7's)

The patched rows are also the **input** embeddings of the
label tokens, and the instruction contains each label token
exactly once (transcripts add ~0.03 extra occurrences/item on
average). At scale s=0.20 with no calibration, the patch
shifts every diagnostic item's label logits by a near-constant
mean offset of **[+43.3, −79.4, +18.4]** (per-class std
~10–12), collapsing the model to all-calm (argmax 34.2%,
alarmed 0%). At s=0.10 the uncalibrated offset is
[+9.5, −27.9, +7.4]. The offset's mean dominates its variance,
so a per-class constant along m-hat can cancel it — the E7
calibration mechanism — but here the correction is large
(gamma_full at s=0.10 = [−0.0513, +0.1514, −0.0400]) and one
application undershoots, so calibration was closed by
fixed-point iteration on the measured residual (below).

## Patch design (round1/patched/, built by patch.py from edits.json)

Per label row c, on BOTH tied copies:

```
Delta_c = 0.10 * ( 2*D_c + bias_centered_c * m_hat ) + gamma_c * m_hat
  D_c            = mu_c − mu   (diagnostic class-mean hidden states)
  bias_centered  = [ +3.064, −0.518, −2.546 ]  (−||mu_c||²/||mu||, centred)
  gamma          = [ +0.00259, +0.19260, +0.05676 ]
                 = gamma_full + gamma_sim + gamma_resid, where
    gamma_full = [−0.0513, +0.1514, −0.0400] cancels the measured
                   mean logit offset of the uncalibrated patch at
                   s=0.10 (real-model forwards, diagnostic only);
    gamma_sim  = [+0.050, 0.000, +0.090] from a fixed-hidden-state
                   coordinate ascent compensating the base rows'
                   unequal mean logits (sim ceiling 90.0% at s=0.10);
    gamma_resid= [+0.0039, +0.0412, +0.0068] from two fixed-point
                   residual-correction steps (t=0.5 then t=1.0)
                   against the sim target mean offset; after the
                   second step the residual mean offset was
                   [−0.64, −1.28, −0.22] logits and a third step
                   *reduced* diagnostic argmax (81.7 → 80.0) —
                   the stated stopping observation (plateau).
```

9 declared edits (E1–E9 in edits.json): 3 direction
(**critical**), 3 bias, 3 calibration. Scalars changed:
3 rows × 1024 × 2 copies = **6,144 of 751,632,384 =
0.00082%** (limit 0.1%).

Criticality prediction, recorded before the ablation ran:
the direction edits are the only per-item, class-conditional
signal in the patch; bias + calibration are per-class
constants along m-hat. Removing the direction edits must
therefore collapse the patched model to a single constant
prediction (≈33%), and replacing them with random same-norm
directions must do the same. Both confirmed (R4-ROUND1.md).

## Groups

- **centroid-readout** (direction + bias edits): installs the
  nearest-centroid classifier the representation already
  supports as the label-row readout. Motivated by: centroid
  88.3% vs dot-product 33.3% on identical hidden states, and
  the constant-attractor failure shape.
- **input-coupling-calibration** (calibration edits):
  cancels the measured mean logit offset the patch induces
  through the input embeddings of the instruction's label
  tokens, and compensates the base rows' unequal priors.
  Motivated by: uncalibrated patches collapsing to a single
  class at every scale tried (s=0.05..0.30).
