# E7 Round 1 — EXPLANATION (teacher/patcher)

Student: fresh Qwen3-0.6B (`~/wsp-exp/e7/work/student-base`), fixed prompt in
`score_joint.py`, greedy, first-label extraction. All geometry, directions and
calibration derived from the **diagnostic split only**. The held-out battery
was never read, listed, or scored.

## First-token geometry findings (probe.py / probe.npz, base model)

- Label token ids: `' code'` = **2038**, `' mixed'` = **9519**, `' model'` = **1614**.
  The two stored copies (`model.embed_tokens.weight`, `lm_head.weight`) are
  byte-identical in the base file (verified) and receive identical edits.
- Base first-token behaviour: the top-1 token is always a label token
  (model 103/120, code 17/120) — **no non-label attractor**, so no suppression
  edits were needed. But the 3-way argmax is 35.0% and `mixed` is **never**
  the argmax: mean label logits by gold class — code items [16.9, 10.9, 18.0],
  mixed [16.5, 11.7, 17.8], model [16.7, 12.9, 18.0] (code/mixed/model order).
  The `mixed` row is handicapped by ~5–7 logits against everything.
- The classes **are** strongly separated in the final hidden state, but in the
  Euclidean sense, not the raw dot-product sense: nearest-centroid on the
  diagnostic hidden states = **84.2%** (code 85 / mixed 82.5 / model 85),
  while `argmax_c h·(mu_c − mu)` = 33.3%. Reason: `||mu|| = 155.3` dwarfs the
  class deviations (`||mu_code−mu|| = 9.04`, `||mu_mixed−mu|| = 4.07`,
  `||mu_model−mu|| = 9.04`; cos(mu_code−mu, mu_model−mu) = −0.899, mixed is
  −0.225 to both). A row edit changes logits by `h·Delta_c` — a bias-free
  linear functional — so the `−||mu_c||²` term of the centroid classifier
  must be emulated by a component along the global mean direction m-hat:
  `h·m-hat = 155.3 ± 3.1` is near-constant, so `gamma_c·m-hat` acts as a
  per-class bias. Simulated on fixed hidden states (sim.py/sim2.py):
  direction-only = 33.3% (all-model), bias-only = 33.3% (all-code),
  direction+bias at scale 0.35 = 84.2% (87.5 / 80 / 85). Both components are
  jointly necessary — this was the criticality prediction, recorded before
  any ablation was run.

## The input-side coupling (the round's central measured fact)

The patched rows are also the **input** embeddings of the label tokens, and
the instruction itself contains tokens 2038/9519/1614 exactly once each.
Measured (probe2/probe3/probe4): the uncalibrated centroid patch shifts the
final hidden state of every diagnostic prompt by `||dh|| ≈ 99–112`
(`||h|| ≈ 157`, cos(h, h') ≈ 0.72), almost independent of scale in
0.10–0.35. The shift is near-constant across items (`||mean dh|| = 96.9`,
per-item residual ≈ 22.5) and its logit effect `mean dh·Delta_c =
[+28.0, −7.5, −20.5]` at s=0.10 swamps the intended term
(`mean h·Delta_c = [−2.2, +4.3, −2.2]`). Every uncalibrated variant therefore
collapses to a single class. The patched geometry itself stays separable
(own-centroid Euclidean on the s=0.10 patched model: 89.2%) — it is the
rows, not the representations, that the coupling breaks.

## Patch design (patched-r1/, built by patch.py from edits.json)

Per label row c, on BOTH tied copies:

```
Delta_c = 0.10 * ( 2*D_c + bias_centered_c * m_hat ) + gamma_c * m_hat
  D_c            = mu_c − mu   (diagnostic class-mean hidden states, probe.npz)
  bias_centered  = [ +3.386, +0.695, −4.081 ]  (−||mu_c||²/||mu||, centred)
  gamma          = [ −0.07945, +0.1836, +0.15975 ]
                 = 0.5 * gamma_full + [0, +0.08, 0],
                   gamma_full = [−0.1589, +0.2072, +0.3195] cancels the
                   measured mean logit offset of the uncalibrated patch;
                   the 0.5 fraction and the +0.08 mixed-only boost were
                   selected by an in-memory line search on diagnostic
                   (search.py/search2.py/search3.py) because the full
                   correction overshoots through the same input coupling.
```

9 declared edits (E1–E9 in edits.json): 3 direction (critical), 3 bias
(critical), 3 calibration (critical). Scalars changed: 3 rows × 1024 ×
2 copies = **6,144 of 751,632,384 = 0.00082%** (limit 0.1%). Row deltas
verified numerically against intent (cos = 1.000, both copies equal).

## Trials (diagnostic; official scorer unless marked argmax-only)

| trial | acc | code | mixed | model | note |
|---|---|---|---|---|---|
| base student | 36.7% | 25% | 0% | 85% | coordinator-consistent |
| dial (incumbent) | 61.7% | 70% | 47.5% | 67.5% | BATTERY.md |
| centroid s=0.35, no calib | 33.3% | 100% | 0% | 0% | all-code collapse |
| centroid s=0.15 / 0.10, no calib | 33.3% | 100% | 0% | 0% | all-code |
| centroid s=0.05, no calib | 44.2% | 75% | 2.5% | 55% | 63/120 outputs contain no label |
| iter1 (centroids of s=0.10 geometry) s=0.35 | 62.5% | 87.5% | 100% | 0% | model absorbed by mixed |
| iter1 s=0.20 | 33.3% | 100% | 0% | 0% | all-code |
| iter2 (centroids of iter1 geometry) s=0.35 | 60.8% | 82.5% | 0% | 100% | oscillation, opposite corner |
| iter2 s=0.50 | 34.2% | 100% | 2.5% | 0% | all-code |
| blends iter0/iter1, iter1/iter2 (w=0.5) | 33.3% / 39.2% | — | 0% / 17.5% | 0% | behaviour does not interpolate |
| projection of Delta ⊥ mean-dh | 41–46% (argmax sim) | 100% | 0% | 25–37% | projection guts the signal |
| full calib gamma (t=1.0), s=0.10 | 33.3% | 0% | 0% | 100% | all-model overshoot |
| s=0.10, t=0.55 (argmax) | 69.2% | 97.5% | 15% | 95% | ridge entry |
| s=0.10, t=0.50, mixed+0.06 (argmax) | 79.2% | 87.5% | 50% | 100% | |
| **s=0.10, t=0.50, mixed+0.08 (argmax search)** | **82.5%** | **82.5%** | **82.5%** | **82.5%** | frozen design |
| **patched-r1, official scorer** | **81.7%** | **80%** | **80%** | **85%** | see below |

Note: identical argmax configs re-measured across searches varied by
~±2 points (bf16 nondeterminism); the scorer number is the deliverable.

## Final result — patched-r1 (score_patched_diag.json)

**Accuracy 81.7% (98/120)** — dial 61.7%, base student 36.7%.
Per-class: code 32/40 (80%), mixed 32/40 (80%), model 34/40 (85%).
Confusion (gold → predicted):
code → {code 32, mixed 7, model 1}; mixed → {code 6, mixed 32, model 2};
model → {code 5, mixed 1, model 34}.
Raw outputs are label-first (e.g. `' model'`, `' mixed code code …'`);
extraction takes the first token's label.

## Self-ablation (diagnostic, official scorer)

Criticality predicted in advance: removing the class-conditional direction
edits leaves only per-class constants (no per-item signal) → collapse;
random same-norm directions → collapse. Both confirmed:

| variant | acc | per-class | confusion |
|---|---|---|---|
| full | 81.7% | 80 / 80 / 85 | above |
| minus-critical (E1,E3,E5 direction edits excluded; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → code |
| minus-random (directions replaced by random same-norm vectors, seed 1234; bias+calibration kept) | 33.3% | 100 / 0 / 0 | all → code |

## Predicted held-out effect

Diagnostic 81.7% with balanced classes. Held-out is a disjoint domain and
was harder for the dial (46.7% vs 61.7%), and this patch sits on a
calibration ridge (at s=0.10, t≈0.65 flips the regime), so I predict a
real but degraded transfer: **held-out accuracy 55–70%, mixed recall
40–70%** (vs dial mixed 7.5%, base 0%), code/model roughly 60–85%.
Stated risk: the observed failure mode of this instrument is never
graceful degradation but single-class collapse; if the held-out hidden
geometry rotates enough that the diagnostic calibration misfires, a
collapse toward ~33% is possible. I put that at roughly a 1-in-4 to
1-in-3 chance. The direction component (the actual class signal) should
transfer better than the calibration constants.

## Process incidents (recorded per doctrine)

- My ~11 trial model directories (1.5 GB each) filled the Thor disk
  (98% → builds failed with ENOSPC; one scorer run then measured the
  stale pre-existing copy and briefly looked like a base-identical
  result). All trial dirs were deleted (35 GB free after), the final
  three models were rebuilt cleanly, and every number above comes from
  the rebuilt artefacts (finalize2.log, ALL_DONE).
- Held-out discipline kept throughout: heldout.jsonl never read/listed/
  scored; all direction/calibration data is diagnostic-only.
