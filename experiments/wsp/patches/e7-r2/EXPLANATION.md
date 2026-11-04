# E7 Round 2 — EXPLANATION (teacher/patcher)

Student: the ADOPTED round-1 specialist (`~/wsp-exp/e7/round1/patched-r1`),
refined by an incremental authored patch built ONLY on a copy
(`patched-r2/`). All geometry, directions and calibration derived from the
**diagnostic split only**. The held-out battery was never read, listed, or
scored. Inputs in round1/ untouched.

## Diagnosis of the 22 round-1 diagnostic failures (from round2/diag_export.jsonl)

Confusion of the failures: code→mixed 7, code→model 1, mixed→code 6,
mixed→model 2, model→code 5, model→mixed 1. Subtype clusters:

- **model / design_note_code_dense: 6 of the 22** (5→code, 1→mixed) — prose
  design notes dense with code vocabulary ("should return a clear error when
  the X is missing", "the function behind the booking form is doing two
  jobs"). ALL 6 items of this subtype that r1 got wrong sit here; the subtype
  is the single biggest failure block.
- **code / prose_identifiers: 4** (→mixed 3, →model 1) — real code whose
  identifiers are prose words (`if story and gentle:`, `def
  light_gentle(warm)`), plus code/config_low_symbol 2, shell_log 1,
  wordy_query 1.
- **mixed failures (8)** are spread: prose_plus_log 2, inline_code_quote 2,
  error_shaped_prose 2 (both →model), prose_plus_block 1, code_long_comments 1.
- 15 of 22 are `boundary: true` items (of 50 boundary items; boundary
  accuracy 70% vs non-boundary 90%).

## Geometry of the CURRENT (patched-r1) model (work/probe_r2.py, probe_r2.npz sha256 523bd8ec…)

- ||mu|| = 136.7 (was 155.3 in base), h·mhat = 136.7 ± 2.5 — the mhat-as-bias
  mechanism still holds. Class deviations grew: ||mu_c − mu|| = code 12.34,
  mixed 5.96, model 12.44 (base: 9.04 / 4.07 / 9.04). Mixed remains the
  geometrically weakest class (smallest deviation).
- Nearest-centroid (Euclidean) on current states: **87.5% train**
  (92.5 / 70 / 100), **81.7% leave-one-out** (82.5 / 62.5 / 100) — LOO is
  exactly the current logit accuracy, so a centroid refresh alone buys
  nothing honest.
- Of the 22 first-token logit failures, **15 are nearest-centroid-CORRECT**
  (their states sit closer to the gold centroid; the r1 rows misread them)
  and 7 are centroid-wrong. The design_note_code_dense failures are
  centroid-correct in 4/4 probed cases (distances favour gold by 0.9–1.7):
  the signal exists in the states; the readout is what fails.
- **A multinomial logistic-regression probe on the same states scores 93.3%
  in 5-fold CV** (92.5 / 87.5 / 100) — a discriminative linear readout
  generalises well beyond both the r1 rows and the centroid rule.
- Split-half validation of candidate increments (fit on 60, test on 60,
  fixed states, 4 splits): centroid increments ≈ base (mean 83.5 vs 84.2 —
  no generalisation, sometimes wreck mixed); **logistic-regression
  increments at α=0.5–0.8 improve every split (+3.3 to +8.3, mean ≈ +5.4)**.
  A naive pairwise code−mixed direction was also simulated and REJECTED:
  it collapses model (h·(mu_code−mu_mixed) is large for model items too).

## Patch design (patched-r2/, built by patch.py from edits.json)

Per label row c, on BOTH tied copies, on top of patched-r1:

```
Delta_c = 0.25 * Wc_c + (gamma_full_c + boost_c) * mhat
  Wc    = class-centred logistic-regression weights (C=3) fit on the
          CURRENT model diagnostic hidden states (directions_r2.npz,
          sha256 5bad8de1a86ff6f2d0323c571f259e88fa6d145ced9863020952876910b8444e)
  gamma_full = [-0.02711, +0.01495, +0.01217] — coupling calibration
          RE-DERIVED for this patch on this model: the direction-only
          patch shifts final hidden states (mean ||dh|| 40-59 measured
          across the trialled alpha range; 58.8 at alpha=0.35/C=10) and
          mean label logits by a centred offset [+3.70, -2.04, -1.66];
          gamma_full cancels that centred offset (t=1.0). Round-1
          constants were not reused.
  boost = model row only, +0.02 — mechanism: under GENERATION, model
          recall was pinned at exactly 85% in every calibrated trial
          (model items flip to code during decoding, although first-token
          label-argmax scores them up to 100%); +0.02 (~+2.7 logits
          pre-coupling) repairs this.
```

Criticality stated in advance (edits.json): direction edits critical
(removing them leaves only constants → large drop); calibration critical
(t=0 trials lose 4–7 pts, mixed sinks); boost non-critical refinement.
Scalars changed this round: 3 rows × 1024 × 2 copies = **6,144 of
751,632,384 = 0.00082%** (limit 0.1%; round-1 scalars in the base not
counted). Row deltas verified against intent: only the two tied tensors
differ from patched-r1, cos(got, intended) ≥ 0.9999 per row/copy (bf16
rounding only).

## Trials (diagnostic; GEN = in-memory generation mirroring the scorer; OFFICIAL = score_joint.py)

| trial | metric | acc | code | mixed | model | note |
|---|---|---|---|---|---|---|
| patched-r1 (base for this round) | OFFICIAL | 81.7% | 80 | 80 | 85 | |
| centroid increment s=0.08–0.10 | fixed-H sim | 88.3% | 85 | 80 | 100 | split-half: does NOT generalise — rejected |
| logreg increment α=1.0 (C=1) | fixed-H sim | 96.7% | — | — | — | train-fit number; CV/split-half is the honest guide |
| logreg C=10 α=0.35 t=1.0 (cand A) | OFFICIAL | 82.5% | 95 | 67.5 | 85 | 3 label-less outputs; argmax had promised 90.8 — generation ≠ argmax |
| logreg C=10 α=0.35 t=0.75 +boost m/m (cand C) | OFFICIAL | 85.0% | 95 | 75 | 85 | superseded |
| 10-config generation sweep (C3/C10, α .25–.35, t .75–1.25) | GEN | 82.5–85.8% | — | — | 85 in ALL | model pinned at 85 under generation — motivated the model boost |
| C3 α=0.25 t=1.25 +model boost 0.02 | GEN | 86.7% | 80 | 85 | 95 | |
| C3 α=0.25 t=1.0 +boost [code .0075, model .02] | GEN | 89.2% | 90 | 77.5 | 100 | REJECTED as final: buys code by trading away mixed, the held-out-weakest class |
| C3 α=0.25 t=1.0 +boost [mixed .015, model .02] | GEN | 88.3% | 77.5 | 90 | 97.5 | mirror rotation; also rejected |
| **FINAL: C3 α=0.25 t=1.0 +model boost 0.02 (patched-r2)** | **OFFICIAL** | **88.3%** | **85** | **80** | **100** | every class ≥ r1; smallest α among top configs; most-regularised direction |

Confusion (patched-r2, diagnostic): code → {code 34, mixed 5, model 1};
mixed → {code 5, mixed 32, model 3}; model → {model 40}. The entire
design_note_code_dense block (6 r1 failures) is repaired; model is perfect.
Remaining 14 failures concentrate exactly where the geometry said the
irreducible boundary lives: prose_identifiers 4 (code with prose-word
identifiers), inline_code_quote 4 (mixed), error_shaped_prose 3 (mixed
shaped like error output), shell_log 1, wordy_query 1, code_long_comments 1.

## Self-ablation (diagnostic, OFFICIAL scorer)

| variant | acc | code | mixed | model |
|---|---|---|---|---|
| full | 88.3% | 85 | 80 | 100 |
| minus-critical (direction edits R2E1–E3 excluded; calibration+boost kept) | 59.2% | 15 | 62.5 | 100 |
| minus-random (directions replaced by random same-norm vectors, seed 1234) | 72.5% | 32.5 | 87.5 | 97.5 |

Both controls degrade sharply, as predicted: the specific discriminative
directions carry the gain (random same-norm directions destroy code,
32.5%). Not a collapse to 33.3% — honestly noted: this ablation is
incremental on top of r1, whose own rows still carry signal underneath,
and the calibration constants without directions actively hurt (59.2% is
BELOW r1s 81.7%). Ablation models were deleted after scoring (disk);
rebuild with `patch.py --exclude R2E1_code_dir R2E2_mixed_dir
R2E3_model_dir` / `patch.py --random-dir 1234`.

## Predicted held-out effect

Diagnostic +6.7 pts (81.7 → 88.3) with no class traded away: code +5,
mixed ±0, model +15, and the single biggest held-out-relevant failure
family (code-vocabulary prose notes read as code — the mirror of the
held-out mixed→code errors) repaired. Direction evidence is split-half
validated, not just train-fit. I predict **held-out +3 to +7 points
(≈87–91%)**, most likely via model staying near-perfect and code/mixed
roughly holding their r1 levels or better. Risks, stated plainly: (1) the
selection searched ~35 generation configs on 120 items, so 1–3 pts of the
diagnostic gain may be selection noise; (2) generation-vs-argmax divergence
means small geometry rotations in the held-out domain can flip borderline
items either way; (3) mixed did not improve on diagnostic — if held-out
mixed degrades, the aggregate could land at the low end. I do NOT predict
a collapse: the patch is small (α=0.25, ||Delta||≈0.23–0.29 per row),
fully calibrated at t=1.0, and every ablation behaved as the mechanism
predicts.
