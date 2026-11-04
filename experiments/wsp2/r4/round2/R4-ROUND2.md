# R4 round 2 — PanicDial specialist patch (slice 46, part R4)

Patcher record, 2026-11-04. Joint: elephant `PanicDial`
(calm / alarmed / stampede). Student: Qwen3-0.6B base,
zero-shot, fixed prompt (`score_student.py`). Patch family 1,
round 1's geometry and dose, calibration regularised.
**Diagnostic split only** was used for every design decision;
held-out was never read, listed, or scored by the patcher;
the only held-out information used is the coordinator's
round-1 verdict aggregates. Teacher calls: **0**.

Adoption bar for this round (stated in advance by the
coordinator): held-out must BEAT round 1's 50.8% overall AND
no class recall may fall more than 5 points below round 1's
per-class recalls (calm 27.5 / alarmed 72.5 / stampede 52.5).
Diagnostic-up + held-out-down = denied as divergence.
This record declares round 2 FINAL for coordinator scoring.
Design and predictions were committed to this branch BEFORE
building (DESIGN.md, commits 0092fb6 and 26ff737).

## Diagnosis: where round 1's generalisation gap lives

Round 1: diagnostic 78.3 → held-out 50.8; calm 62.5 → 27.5
(27/40 held-out calm answered alarmed), stampede 85.0 → 52.5
(17/40 answered alarmed), alarmed 87.5 → 72.5. One-directional
collapse into alarmed in the unseen world.

Probes run for this round (diagnostic only):

- **LOO nearest-centroid** on base hidden states: 85.8%
  (calm 75.0 / alarmed 95.0 / stampede 87.5). Per subtype:
  `drill_notice` 0/4 even leave-one-out — a representation
  limit at the final hidden state, NOT chased (see
  EXPLANATION.md); `negated_alarm` 3/5, `work_routine` 3/7,
  `technical_cascade` 3/6.
- **Split-half direction stability**: cos(D_half1, D_half2)
  = 0.745 / 0.735 / 0.824 (calm/alarmed/stampede) — class-mean
  directions carry real sampling noise at n=40/class; a
  split-half sign-agreement denoised variant was cross-tested
  and not adopted (neutral at the operating points tried).
- **Cross-fitted simulation** (5-fold stratified partition;
  all geometry + sim calibration refit per fold on 96 items,
  scored on the 24 held out from fitting; fixed-H, gamma_sim
  only): pure centroid 82.5; round-1 recipe 82.5; s=0.05
  82.5 / s=0.15 84.2 / s=0.20 84.2; denoised-D 83.3;
  dir-coeff 0.15: 78.3 / 0.25: 80.8 / **0.30: 85.8** (most
  balanced per-class). An earlier run of this instrument had
  a fold bug (per-fold reshuffles → overlapping test sets, 40
  items never predicted, aggregate 53.3 contradicting
  fold-wise 0.67–0.83); caught, fixed to a single partition,
  all numbers from the fixed run.

## Trials (all real-model, diagnostic; argmax = 3-label
## first-token argmax, scorer = official score_student.py)

| trial | argmax | scorer | per-class (scorer) | note |
|---|---|---|---|---|
| round 1 (control, from its record) | 81.7 | 78.3 | 62.5 / 87.5 / 85.0 | adopted |
| dir 0.30, calib re-derived, fixed-point to convergence | 65.0 | — | — | DESIGN's primary; coupling distortion (below) |
| denoised-D s=0.15 | 69.2 | — | — | predeclared fallback; same failure |
| dir 0.25, bias 0.10 | 66.7 | — | — | predeclared CV grid member |
| dir 0.15, bias 0.075 (dose reduction) | 77.5 | 56.7 | 50.0 / 92.5 / 27.5 | generation collapse: spaced rows lose to bare `alarmed` token; rejected by floor rule |
| dir 0.10, bias 0.05 (s=0.05) | 70.8 | — | — | dose curve point |
| **round 2 FINAL: round-1 dose/geometry, gamma_resid × 0.5** | — | **72.5** | **65.0 / 75.0 / 77.5** | Amendment A design |

Deviations from the frozen DESIGN, recorded not hidden:
(1) the DESIGN capped residual calibration at two steps,
assuming round-1-like convergence; at dir 0.30 the residual
contracted geometrically (~0.28×/step) from a 14× larger
start, so iteration continued to round 1's actual stopping
rule (converged ≤1.3 logits, or a step lowers argmax) — the
config still failed. (2) After the fallback chain failed,
Amendment A (committed before building it) changed the
design to the calibration-shrinkage lever named in the
round-2 brief itself; the dir-0.25 and s=0.05/0.075 builds
were predeclared CV-grid members run to complete the dose
curve, not a fresh search.

**Mechanism finding (this round's main evidence):** the
fixed-H simulation is blind to the patch's dominant
real-model error term. Per-item input-coupling offset std
grows with delta norm (dir 0.30: norms 1.77–2.02, std
7.4–10.6 logits; round 1: norms 1.18–1.35, std 4.9–7.2),
and the real-model dose curve peaks exactly at round 1's
dir 0.20. Amplifying the direction — the cross-fitted sim's
top pick — is unrealisable on the tied-embedding student:
the same rows are the instruction's input embeddings, and
past dir ≈ 0.20 the representation distortion eats the
signal. Any future round on this student should treat
dir 0.20 as a measured ceiling, not a choice.

## Final result — diagnostic (official scorer)

**Accuracy 72.5% (87/120)** — round 1: 78.3%, base student
30.0%, incumbent dial 23.3%. Per-class: calm 26/40 (**65.0%**,
round 1: 62.5), alarmed 30/40 (75.0%, round 1: 87.5),
stampede 31/40 (77.5%, round 1: 85.0). Boundary subset:
**64.0% (32/50)** (round 1: 72.0%). Confusion (gold →
predicted): calm → {calm 26, alarmed 11, stampede 3};
alarmed → {alarmed 30, calm 10}; stampede → {stampede 31,
alarmed 9}.

The diagnostic trade is the design working as stated, not
an accident: −5.8 points overall bought by returning
surplus from the two strong classes, calm (the held-out-
fragile class) up +2.5, and the constant alarmed boost —
the suspected held-out poison — halved. Residual errors:
`negated_alarm` 0/5 and `drill_notice` 0/4 unchanged
(representation limit, probe evidence in EXPLANATION.md);
`fast_water` 3/7, `slow_burn_technical` 3/7.

Dose: 9 edits, 3 rows × 1024 × 2 tied copies = **6,144
scalars of 751,632,384 = 0.00082%** (limit 0.1%). Verified
after build: exactly the two tied tensors differ from base,
exactly rows {19300, 81040, 21206} in each. `patch.py`
rebuilds the patched directory from the pristine base;
`directions.npz` is byte-identical to round 1's.

## E4 self-check (diagnostic, official scorer)

Prediction recorded in EXPLANATION.md before running:
removing the direction edits, or replacing them with random
same-norm directions, collapses the model to a constant
prediction. **Confirmed exactly:**

| variant | acc | per-class | confusion |
|---|---|---|---|
| full patch | 72.5% | 65.0 / 75.0 / 77.5 | above |
| minus-critical (3 direction edits excluded; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → calm |
| minus-random (directions replaced by random same-norm vectors, seed 1234; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → calm |

The diagnostic effect follows the critical set.

## Predicted held-out effect (for THIS final config,
## recorded in DESIGN.md Amendment A before building)

Held-out **53–62%** overall (round 1: 50.8), calm **35–50%**
(round 1: 27.5 — the class this design aims at), alarmed
68–78%, stampede 50–62% (floor from the adoption bar:
47.5). Stated risk: the bet is narrow — if round 1's
residual correction was mostly climate (a real offset that
transfers) rather than diagnostic weather, this round
scores slightly BELOW round 1 on held-out and is denied,
and the dose-curve/coupling findings above are the round's
durable output either way.

## Artefacts

- Patched model (complete dir, built by patch.py from
  pristine base): Thor `~/wsp-exp16/r4/round2/patched/`
- In this directory (`experiments/wsp2/r4/round2/`):
  `DESIGN.md` (design + Amendment A, committed before
  building), `patch.py`, `edits.json`, `directions.npz`,
  `EXPLANATION.md`, `manifest.json`, this record, and
  scorer outputs `score_patched_diag.json`,
  `score_abl_minus_critical_diag.json`,
  `score_abl_minus_random_diag.json`.
- Working files (probes, CV sim, all trial build scripts
  and their JSON logs) remain on the Thor at
  `~/wsp-exp16/r4/round2work/`.

## Marginal cost

Teacher calls: **0**. Worker wall time: 2026-11-04
07:44–08:00 UTC approx (16 min, incl. all probe/CV/build/
scoring runs on the Thor; GPU shared, no foreign process
touched). Governance decisions: this patch is submitted
as one proposal (manifest.json) for the coordinator's
held-out scoring against the pre-stated round-2 bar;
adoption is the coordinator's call from that verdict.
