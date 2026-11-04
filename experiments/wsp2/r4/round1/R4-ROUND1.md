# R4 round 1 — PanicDial specialist patch (slice 46, part R4)

Patcher record, 2026-11-04. Joint: elephant `PanicDial`
(calm / alarmed / stampede). Student: Qwen3-0.6B base,
zero-shot, fixed prompt (`score_student.py`). Patch family 1
(class-mean centroid directions + emulated bias on the
label-token rows of the tied embedding), per
`experiments/wsp/PATCH-PROTOCOL.md` and the E7 recipe
(`experiments/wsp/SLICE43-E7.md`). **Diagnostic split only**
was used for every design decision; held-out was never read,
listed, or scored by the patcher; validation was seen only
as the builder's published aggregates. Teacher calls
(strong-model consultations beyond this session): **0**.

Pre-stated success bar (CRITERIA.md + Amendment A1, judged
by the coordinator on held-out): held-out >= 42.5% (better
incumbent = student's 32.5%, +10) with no class traded away.
This record declares round 1 FINAL for coordinator scoring.
No round 2 was attempted (E7's round-2 divergence is the
standing warning).

## Diagnosis (diagnostic, n=120)

Student baseline reproduced from the builder's artefacts and
re-scored in this session with the official scorer on the
pristine base: **30.0% — calm 0/40, alarmed 36/40,
stampede 0/40**; confusion calm→{alarmed 38, none 2},
alarmed→{alarmed 36, calm 4}, stampede→{alarmed 40}.
Identical to the builder's `results/student_diagnostic.json`.

Failure structure (probe on the base model, answer position):

- First-token argmax over the three label rows is **constant
  alarmed on all 120 items**. Mean label logits by gold class
  differ by <1 logit between classes while the alarmed row
  holds a ~+8 (vs calm) / ~+15 (vs stampede) prior on every
  input. Two attractors are missing, not mis-weighted — the
  E7 shape.
- The representation already separates the classes:
  nearest-centroid (Euclidean) on final hidden states =
  **88.3%** (calm 77.5 / alarmed 97.5 / stampede 90.0);
  cosine 89.2%; raw dot-product readout 33.3%. The failure
  is a readout failure (G3 in the R2 grading), exactly the
  grade family 1 addresses.
- Feature tracking: the base answer tracks nothing per-item
  (zero prediction variance). The gold-defining signals are
  present in the transcripts — corroborators (r=+0.95 with
  gold stampede), distinct authors (+0.83), trailing density
  (+0.74), cascade heat (+0.53) — and alarm-word density
  *anti*-correlates with genuineness (calm rooms average
  1.48 distinct alarm hits vs alarmed 0.60 / stampede 0.97),
  so the incumbent dial's lexicon weighting and the student's
  prior are both structurally blind here, in different ways.

## Method (summary; full mechanism in EXPLANATION.md)

1. Probe: class-mean hidden states at the answer position
   from diagnostic only → centroid directions D_c, global
   mean direction m-hat, bias_centered from −||mu_c||²/||mu||.
2. Fixed-hidden-state simulation: direction+bias alone peaks
   at 62.5% (s=0.10) because the base rows' priors survive;
   adding per-row calibration constants (coordinate ascent in
   sim) reaches 90.0% at s=0.10, 91.7% at s>=0.20. Smallest
   plateau scale family carried forward: s=0.10.
3. Real-model calibration: the patch's input-side coupling
   (label rows are also the instruction tokens' input
   embeddings) shifts label logits by a near-constant mean
   offset ([+9.5, −27.9, +7.4] at s=0.10, uncalibrated) that
   collapses the uncalibrated patch to one class. gamma was
   set to cancel it (gamma_full, measured), plus the sim
   calibration, then closed by two fixed-point residual
   steps against the sim target offset.
4. **Stopping observation (stated at declaration):** after
   the second residual step the residual mean offset was
   ≤1.3 logits on every class; a third correction step
   *lowered* diagnostic argmax (81.7% → 80.0%) and a final
   micro-boost probe on the weak class (calm ±0.01/0.02)
   only traded classes (calm +5 ⇔ alarmed −10). Gains had
   plateaued; the design froze.

Trials (diagnostic; argmax = first-token 3-label argmax
proxy, scorer = official `score_student.py` generation):

| trial | acc | calm | alarmed | stampede | note |
|---|---|---|---|---|---|
| base student (scorer) | 30.0% | 0 | 90.0 | 0 | builder-identical |
| base (argmax) | 33.3% | 0 | 100 | 0 | constant attractor |
| centroid sim s=0.10, no calib | 62.5% | 50 | 100 | 37.5 | fixed-H |
| centroid sim s=0.10 + gamma_sim | 90.0% | 82.5 | 97.5 | 90 | fixed-H ceiling |
| real s=0.20/0.30, gamma_sim only | 35–37% | 95+ | 0 | 8–15 | coupling collapse to calm |
| real s=0.10, gamma_full(t=1)+sim | 75.8% | 82.5 | 45 | 100 | argmax |
| + residual step t=0.5 | 76.7% | 80 | 55 | 95 | argmax |
| + residual step t=1.0 (**frozen**) | **81.7%** | 70 | 82.5 | 92.5 | argmax |
| + third residual step | 80.0% | 65 | 82.5 | 92.5 | plateau — rejected |
| frozen ± calm micro-boost | 75.8–80.0% | 75–80 | 60–72.5 | 87.5–92.5 | class trading — rejected |
| **patched round 1 (scorer, FINAL)** | **78.3%** | **62.5** | **87.5** | **85.0** | generation |

## Final result — diagnostic (official scorer)

**Accuracy 78.3% (94/120)** — base student 30.0%, incumbent
dial 23.3%. Per-class: calm 25/40 (62.5%), alarmed 35/40
(87.5%), stampede 34/40 (85.0%). Boundary subset: **72.0%
(36/50)** vs base 26%. Confusion (gold → predicted):
calm → {calm 25, alarmed 12, stampede 3};
alarmed → {alarmed 35, calm 5};
stampede → {stampede 34, alarmed 6}.

No class is traded away against the student's own pattern:
calm rises 0 → 62.5 and stampede 0 → 85.0 while alarmed
holds at 87.5 (base 90.0). Residual errors concentrate where
the centroid itself is weakest: calm subtypes
`negated_alarm` 0/5 and `drill_notice` 0/4 (stood-down /
scheduled alarm language still reads alarmed — negation and
modality are the readout's blind spot, mirroring the
incumbent's D2 defect in miniature), and stampede
`fast_water` 4/7. All other subtypes score >= 3/5, including
`technical_cascade` 5/6 (incumbent dial: reads 0.13–0.19,
calm) and `single_loud_voice` 6/6 (not stampede).

Dose: 9 edits, 3 rows × 1024 × 2 tied copies = **6,144
scalars of 751,632,384 = 0.00082%** (limit 0.1%). Every edit
is enumerated in `edits.json` and reversible: `patch.py`
rebuilds the patched directory from the pristine base.

## E4 self-check (diagnostic, official scorer)

Prediction recorded in EXPLANATION.md before running: the
direction edits are the patch's only per-item signal, so
removing them — or replacing them with random same-norm
directions — must collapse the model to a constant
prediction. **Confirmed exactly:**

| variant | acc | per-class | confusion |
|---|---|---|---|
| full patch | 78.3% | 62.5 / 87.5 / 85.0 | above |
| minus-critical (3 direction edits excluded; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → calm |
| minus-random (directions replaced by random same-norm vectors, seed 1234; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → calm |

The diagnostic effect follows the critical set.

## Predicted held-out effect

Diagnostic 78.3% with all classes alive. Held-out is a
disjoint world (hostel/depot/campsite pools) and was harder
for both baselines' *relative* patterns; this patch sits on
a calibration fixed point whose residual was ≤1.3 logits, so
I predict real but degraded transfer: **held-out 55–70%,
stampede recall 50–80%** (vs student 0%), calm the most
fragile class (45–65%). Stated risk, same as E7's: this
instrument's failure mode is single-class collapse, not
graceful decay; if held-out hidden geometry rotates enough
that the diagnostic calibration misfires, a collapse toward
~33% is possible (roughly 1-in-4). The direction component
should transfer better than the calibration constants.

## Artefacts

- Patched model (complete dir, built by patch.py from
  pristine base): Thor `~/wsp-exp16/r4/round1/patched/`
- In this directory (`experiments/wsp2/r4/round1/`):
  `patch.py`, `edits.json`, `directions.npz`,
  `EXPLANATION.md`, `manifest.json`, this record, and
  scorer outputs `score_patched_diag.json`,
  `score_base_rescore_diag.json`,
  `score_abl_minus_critical_diag.json`,
  `score_abl_minus_random_diag.json`.
- Working files (probe/search scripts + logs) remain on the
  Thor at `~/wsp-exp16/r4/patchwork/`.

## Marginal cost

Teacher calls: **0**. Worker wall time: 2026-11-04
07:31–07:43 UTC (~12 min, incl. all probe/search/scoring
runs on the Thor; GPU shared, no foreign process touched).
Governance decisions: this patch is submitted as one
proposal (manifest.json) for the coordinator's held-out
scoring; adoption is the coordinator's call from that
verdict.
