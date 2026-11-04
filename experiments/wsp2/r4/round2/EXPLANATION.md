# R4 Round 2 — EXPLANATION (patcher)

Student: fresh Qwen3-0.6B (`~/wsp-exp/models/Qwen3-0.6B`, read-only),
fixed prompt in `experiments/wsp2/r4/score_student.py`, greedy,
first-label extraction. All geometry, directions and calibration
derived from the **diagnostic split only** (120 items). The
held-out split was never read, listed, or scored by this patcher;
validation was seen only as the builder's published aggregates.
Round 1's record, artefacts and the coordinator's held-out
AGGREGATES (50.8 overall; calm 27.5 / alarmed 72.5 / stampede 52.5;
confusions calm→alarmed 27/40, stampede→alarmed 17/40) were the
only held-out information used.

## What round 2 changes vs round 1 — one thing

Round 1: `Delta_c = 0.10 * (2*D_c + bias_centered_c * m_hat) + gamma_c * m_hat`
with `gamma = gamma_full + gamma_sim + gamma_resid`
= [+0.00259, +0.19260, +0.05676].

Round 2: **identical directions, identical dose, identical bias**
(same `directions.npz`, sha256 e2c17cf4… — the geometry file is
byte-identical to round 1's). The only change is the calibration:

```
gamma_r2 = gamma_full + gamma_sim + 0.5 * gamma_resid
         = [+0.00065, +0.17202, +0.05340]
  gamma_full  = [-0.0513, +0.1514, -0.0400]   (round 1's measured
                input-coupling cancellation — a prompt-mechanism
                constant, world-independent)
  gamma_sim   = [+0.050, 0.000, +0.090]       (round 1's fixed-H
                coordinate ascent vs the base rows' priors)
  gamma_resid = [+0.0039, +0.0412, +0.0068]   (round 1's two
                fixed-point residual steps, fitted to the
                diagnostic mean offset; HALVED here)
```

Why this component: it is the only part of round 1's patch that
was fitted iteratively against diagnostic outcomes (it bought
+5.0 diagnostic argmax points, 76.7 → 81.7, in round 1's own
search record), and its largest term is a constant boost to the
alarmed row (gamma_resid_alarmed × (h·m-hat) ≈ +7.6 logits on
every input, whatever the room). Round 1's held-out failure was
one-directional — both other classes collapsing INTO alarmed —
which is the signature of a constant alarmed boost that was
calibrated to one world's mean geometry and overshoots in
another. Halving (not zeroing) the residual keeps the part of
the correction that cancels a real measured offset while
shrinking the diagnostic-fitted overshoot; the shrinkage factor
0.5 was stated in DESIGN.md Amendment A before this patch was
built or scored.

## What round 2 tried first, and why it is not this patch

The frozen DESIGN (committed before any build) chose direction
amplification (coefficient 0.20 → 0.30), ranked first by a
5-fold cross-fitted fixed-H simulation (85.8 vs round-1 recipe
82.5) whose folds refit all geometry on 96 items and score 24
held out from fitting. On the REAL model it failed, as did the
predeclared fallback chain (full table in R4-ROUND2.md):

- dir 0.30 converged calibration: argmax 65.0 (round 1: 81.7)
- denoised-D s=0.15: argmax 69.2
- dir 0.25: argmax 66.7
- dir 0.15 (dose reduction): argmax 77.5 but official scorer
  56.7 — at that dose the spaced label rows no longer dominate
  the bare `alarmed` token in free generation (stampede 27.5)

Measured mechanism: the patch's input-side coupling distortion
(per-item std of the label-logit offset) grows with delta norm —
dir 0.30: norms 1.77–2.02, offset std 7.4–10.6 logits; round 1:
norms 1.18–1.35, std 4.9–7.2. Fixed-H simulation holds hidden
states frozen and therefore cannot see this term at all; it
ranked the failing config first. The real-model diagnostic dose
curve (argmax: dir 0.10 → 70.8, 0.15 → 77.5, **0.20 → 81.7**,
0.25 → 66.7, 0.30 → 65.0) shows round 1 already sits at the
realisable dose optimum. Round 2's conclusion: the gap is not
a dose problem; it is a fitted-constants problem, and the
calibration shrinkage above is the lever that remains.

## Groups

- **centroid-readout** (direction + bias edits, critical =
  direction edits): unchanged from round 1. Installs the
  nearest-centroid classifier the representation already
  supports (LOO centroid 85.8% on diagnostic hidden states)
  as the label-row readout.
- **input-coupling-calibration** (calibration edits): cancels
  the measured mean logit offset the patch induces through
  the input embeddings of the instruction's label tokens, and
  compensates the base rows' unequal priors — with the
  residual (diagnostic-fitted) part halved vs round 1.

Criticality prediction, recorded before the ablation ran: as in
round 1, the direction edits are the only per-item,
class-conditional signal; removing them — or replacing them
with random same-norm directions — must collapse the model to
a single constant prediction (≈33%). Both confirmed
(R4-ROUND2.md): minus-critical 33.3% all-calm, minus-random
33.3% all-calm.

## The calm blind spot, with probe evidence

Round 1 missed the diagnostic calm subtypes `negated_alarm`
(0/5) and `drill_notice` (0/4); round 2's scorer shows the same
0/5 and 0/4. Leave-one-out nearest-centroid on base hidden
states (each item classified by centroids fitted without it)
scores drill_notice **0/4** and negated_alarm 3/5: scheduled-
drill modality is not separated from the other classes by
class-mean geometry at the final hidden state — a
REPRESENTATION limit for this readout family, not a margin
that a readout patch can buy back — while negation is
partially separated geometrically (3/5) but not reachable
through this readout in free generation. No subtype-specific
edits were attempted: fitting two subtypes (9 items) would be
exactly the diagnostic-tuning this round exists to avoid.
