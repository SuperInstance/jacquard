# Phase 17 W1 — re-coaching round 2 for the model/code dial

Patcher record. Candidate: `p17-w1-r2` on the Thor at
`~/wsp-exp17/w1-r2/patched-r2` (model.safetensors sha256
`8f343221a3908d7d490152b49e791721111c53d2de60f677deacef837f8408c2`).
Manifest: `experiments/wsp3/w1-r2/edits.json` (same directory as
this file). The trigger, grading, and criteria are in
W1-GRADING.md / CRITERIA.md; nothing here re-opens them.

All scores in this record are **diagnostic / in-sample**: the
candidate was fitted on the two diagnostic sets it is scored on.
They are reported to show the refit did what it was aimed at,
never as generalisation. The two held-outs (live graded sample,
66; battery held-out, 120) belong to the coordinator and were
never opened, listed for fitting, or scored by the patcher.

## Why this round exists

Round 1 (E7 round 1, adopted Phase 15) scored 84.2% on the
battery held-out and 27.3% blind-graded on live traffic, with
the model class dead (0/26). The battery is short messages;
live traffic is long documents (live-diagnostic prompt lengths
36–6,590 tokens, median live item 4,579 chars). This round is a
refit of the same patch family with live-distribution
diagnostic data married in.

## Construction (round 1's family, replicated)

Same construction as E7 round 1, adapted in paths and data
only (`probe.py` / `make_edits.py` / `patch.py` →
`~/wsp-exp17/w1-r2/{probe_r2,make_dirs,patch_r2}.py`; scorer =
the unmodified `score_joint.py`, fixed prompt, greedy, first
label wins):

1. Probe the pristine base (Qwen3-0.6B, byte-identical to the
   E7 student-base, sha256 f47f7117…) for final hidden states
   and label logits on the fit set.
2. Class centroids over the fit set; per label row c, on BOTH
   tied copies (`model.embed_tokens.weight`, `lm_head.weight`):
   `Delta_c = scale*(2*D_c + bias_centered_c*m_hat) + gamma_c*m_hat`,
   with `D_c = mu_c − mu`, the bias term emulating the
   nearest-centroid `−||mu_c||²` term along the global-mean
   direction, and `gamma` cancelling the input-side coupling
   offset round 1 measured (label rows are also the input
   embeddings of the instruction's label tokens).
3. 9 declared edits (3 direction + 3 bias + 3 calibration),
   6,144 scalars of 751,632,384 (0.00082%). Verified after
   build: only the two tied tensors differ from base, exactly
   3 rows, cos(got, intent) = 1.00000 per row/copy; row delta
   norms 3.55 (code) / 2.20 (mixed) / 3.30 (model).

## The distribution marriage — weighting, stated and measured

Fit set (145 items, diagnostic only): battery diagnostic 120
(40/40/40) + live diagnostic 25 (code 15 / model 9 / mixed 1).

Geometry measured before choosing (probe_r2.npz): the two
sources' global means nearly coincide (cos 0.978) but the
class-deviation directions rotate hard between short messages
and long documents — cos(battery dev, live dev) = +0.136 code,
+0.149 model, −0.078 mixed. Battery centroids tested on live
states score 52.0% (model 0/9): the wild failure, reproduced
in the geometry. Live deviations are larger (model 18.3 vs
battery 9.0). The single live mixed item is an extreme
outlier: deviation 36.5 from the live mean, against battery
class deviations of 4–9.

Four weightings were computed and simulated on fixed hidden
states (simulation ignores coupling; it ranks estimators, it
decided nothing alone):

| scheme | battery sim | live sim | verdict |
|---|---|---|---|
| A battery-only (round 1 refit) | 82.5–84.2 | 56.0, model 11% | the failure itself |
| B pooled, equal per item | 87.5 (s=0.10) | 88.0 | **selected** |
| B2 pooled, live ×2 | 67.5 | 92.0 | rejected: spends battery code/model (50/55%) — the E7 round-2 trade in new clothes |
| C per-class source-balanced centroids (0.5/0.5; mixed 0.85/0.15) — the pre-registered first choice | 44–48, model 0% | 88–92 | rejected on measurement: averaging raw centroids across rotated distributions lands off-manifold; the outlier mixed item at 0.15 still drags the mixed centroid (norm 36.5) and the class-balanced mean built from it breaks battery model entirely |
| C2 deviation-averaged (mixed from battery only) | 75.8 | 92.0 | rejected: compromise directions are mediocre where the retention check lives; B dominates it on the registered rule |

**Selected weighting (scheme B):** round 1's pooled-centroid
construction applied verbatim to the married set — every fit
item equal weight. By count that is battery 83% / live 17%,
but the pull is not the count: live items carry deviations
2× the battery's, so live geometry moves the pooled model and
code centroids well beyond 17% (fixed-H simulation: live
model recall 11% → 78% at s=0.10 before calibration). One
asymmetry is deliberate: the calibration offset is measured
**source-balanced** (mean of the two per-source mean offsets),
so the 25 live items hold half the calibration voice — the
coupling they suffer is the larger one (+24.8/−38.2/−19.2
logits at s=0.20) and a pooled mean would let the battery
understate it 5:1.

**How mixed is kept alive:** mixed's pooled centroid is
40/41 battery by count — battery evidence is the only
substantive mixed evidence there is, and the refit keeps it
that way. Concretely: the one live mixed item enters at its
natural pooled weight (1/41 of the mixed centroid ≈ 2.4%)
and no more; every attempt to raise its voice (0.15 in
centroid space, 0.15 in deviation space) measurably poisoned
battery mixed (28–50% simulated recall), because that item
is a geometric outlier whose deviation is near-orthogonal
to the battery mixed direction. The shipped config was also
required to clear a battery-mixed floor at selection (below),
and clears it at 77.5% generation-scored. The registered
mixed-boost contingency (+0.04 on the mixed calibration row)
was **not** triggered and not used.

## Dose and search discipline

- Dose: scale **0.20**, the measured ceiling from Phase 16
  R4 metrology for direction dose on this tied-embedding
  student — at the ceiling, not above it.
- Search: 9 registered grid points (s ∈ {0.10, 0.15, 0.20} ×
  t ∈ {0.5, 0.75, 1.0}, in-memory first-token argmax) + 5
  refinement points around the one ridge the grid found
  (s=0.20: t ∈ {0.9, 1.0, 1.1}; s=0.15: t ∈ {0.85, 1.0}) —
  14 configurations total, against E7 round 2's ~35. Two
  finalists were generation-scored with the official scorer;
  selection rule, stated before generation scoring: maximise
  min(battery-diagnostic, live-diagnostic) accuracy subject
  to per-class floors (battery code/model ≥ 60%, battery
  mixed ≥ 55%, live code ≥ 60%, live model ≥ 55%; live mixed
  n=1 carried as a named exception, not a floor).
- Finalists (generation, diagnostic): A (s=0.20, t=0.90):
  battery 79.2 live 88.0, min 79.2, battery balanced
  80.0/77.5/80.0. B (s=0.20, t=1.0): battery 78.3 live 76.0,
  min 76.0, battery code 62.5. **A ships.** Its argmax profile
  was the ridge centre (78/78/78 battery) — balance was the
  tie-break evidence, not a post-hoc preference.
- gamma_full (s=0.20) = [−0.27521, +0.42316, +0.21306];
  shipped gamma = 0.90 × gamma_full =
  [−0.24769, +0.38084, +0.19175] (code/mixed/model).
  bias_centered = [+3.8256, −2.6776, −1.1479].

## Diagnostic scores (in-sample; official scorer, generation)

Battery diagnostic (n=120), generation:

| model | overall | code | mixed | model |
|---|---|---|---|---|
| base student | 36.7%* | 25%* | 0%* | 85%* |
| round-1 specialist | 81.7%* | 80%* | 80%* | 85%* |
| **re-coached r2** | **79.2%** | **80.0%** | **77.5%** | **80.0%** |
| r2 minus-critical (directions removed) | 33.3% | 100% | 0% | 0% |
| r2 minus-random (random same-norm directions) | 33.3% | 100% | 0% | 0% |

(*from the E7 record, SLICE43-E7.md / round-1 EXPLANATION.md.)
r2 confusion: code → {code 32, mixed 7, model 1};
mixed → {code 8, mixed 31, model 1};
model → {code 5, mixed 3, model 32}. The battery cost of
the marriage is −2.5 points against round 1 in-sample, paid
as −2.5 mixed / −5 model at +0 code: small, spread, and no
class traded away — the shape the retention discipline asks
for, in-sample. The held-out will say whether it holds.

Live diagnostic (n=25; code 15 / model 9 / mixed 1), generation:

| model | overall | code | mixed | model |
|---|---|---|---|---|
| base student | 36.0% | 0/15 | 0/1 | 9/9 |
| round-1 specialist | 44.0% | 10/15 | 0/1 | 1/9 |
| **re-coached r2** | **88.0%** | **14/15** | **0/1** | **8/9** |
| r2 minus-critical | 60.0% | 15/15 | 0/1 | 0/9 |
| r2 minus-random | 60.0% | 15/15 | 0/1 | 0/9 |

r2 confusion (live): code → {code 14, model 1};
model → {model 8, code 1}; mixed → {model 1}.
The dead class is repaired in-sample (1/9 → 8/9) and code
improves with it; the ablations collapse to all-code on both
sources, as the mechanism predicts (directions carry the
per-item signal; constants alone pick the majority basin).

The one live-diagnostic miss worth naming: the single mixed
item (c0102) is read as model by every model in this record,
including constructions whose mixed centroid is purely
battery. It is a 25 KB cumulative report that is half
pipeline log, half model-behaviour analysis; on the fitted
geometry it sits far from every mixed centre (see the
outlier measurement above). No configuration in the search
recovered it without spending a battery class, so it stands
as a known in-sample miss, not a tuned-around one.

## Recorded prediction (before coordinator scoring)

Stated for the coordinator's two held-outs, with reasons:

- **Live graded sample (66; code 20 / mixed 20 / model 26):**
  overall **55–70%** (point ~62%): code 70–85%, model
  65–85%, mixed 35–60%. Reasoning: the live code/model
  repair rests on 24 live documents from the same corpus
  population and the same long-document geometry that the
  probe shows is genuinely separable (live-fitted centroids
  separate live states at 96%); the graded sample's centre
  of gravity is the same task. Mixed is the named risk: it
  is 20/66 of the sample but rests on battery evidence
  alone, and the cross-source mixed direction barely
  transfers (cos −0.078) — the 35–60% band is battery-mixed
  transfer, discounted. Even the low end clears the
  incumbent (30.3%) and round 1 (27.3%) by ~25 points; the
  high end still likely misses the strict SURVIVES-CONTACT
  bar (≥74.2% with no dead class). Expectation stated
  plainly: major repair, probably not full survival, with
  no class at zero.
- **Battery held-out (retention check, 120, 40/40/40):**
  overall **72–82%**, mixed **65–85%**, no class below 60%.
  Reasoning: diagnostic battery is 79.2% and balanced rather
  than tilted (the E7 round-2 failure announced itself
  in-sample as a tilt; there is none here), round 1's
  diagnostic→held-out gap for this family was +2.5, and the
  dose/calibration sit at a ridge centre, not an edge. A
  mixed collapse of the round-2 kind (<55%) is not
  expected; a small retention tax against round 1's 84.2%
  (−2 to −10) is, and is the honest price of the marriage.

## Reversibility and containment

The candidate is a fresh copy built from the pristine base;
round 1's artefact and the base model were only ever read
(scoring/probing), never mutated (base sha256 verified
unchanged by identity with the E7 student-base). Rollback =
discard `~/wsp-exp17/w1-r2/patched-r2`. Nothing was promoted
to any serving role; adoption is the coordinator's and
Casey's decision, per charter.

## Process incidents (recorded per doctrine)

- First probe build died silently twice on long-document
  batches (full-sequence logits + eager attention on
  6.5k-token documents against a loaded unified-memory
  bench). Fixed by batch-1 forwards with SDPA and
  last-position-only logits — same values, a fraction of
  the memory. The longest live document forwards in 0.7 s
  in that form.
- Long Thor runs were SIGTERM-killed three times (the
  W1-CORPUS.md lane hit the same); all scoring after the
  first kill ran as short chunked runs (live items in
  chunks of 5; the heaviest chunk — five model documents
  including the 25,791-char item — scored as singles, the
  fleet's established micro-chunk workaround). Every number
  above comes from a completed, written score file.
- The refinement search overwrote the first search's JSON
  summary (same output path); the full first-search table
  survives in `work/search_r2.log` on the Thor and is the
  record of the grid.
- Thor disk stayed tight throughout (26–27 G free); trial
  candidate and ablation model directories were deleted
  after scoring. Only `patched-r2` remains as a model copy
  from this round.

Artefacts on the Thor (`~/wsp-exp17/w1-r2/`): `patched-r2/`
(sha256 above), `work/probe_r2.npz`
(a7f1a662…), `work/directions_r2.npz` (0f5720e4…),
`work/final_config.json` (6a074a11…), all score JSONs and
logs under `work/`, scripts at the lane root. In the repo:
this file, `w1-r2/edits.json`, and the governance pair.
