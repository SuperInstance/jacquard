# Phase 16, slice 46 (R3) — authored neuron surgery on the dates task

Worker role: teacher/patcher for family 2 (authored edits confined
to probe-identified MLP neurons/gates), tested against the
procedure boundary on T2 (date/interval arithmetic, Phase 15 E5).
Held-out scoring is the coordinator's, never this worker's.

**Verdict, up front: NO PATCH IS DECLARED.** Activation probing
finds neurons that *discriminate* success, failure and category
well beyond a permutation null — but eleven intervention trials
on those neurons, at doses from 0.0018% to 0.0267% of parameters,
never improve any failing category on the diagnostic split. The
best configuration's diagnostic delta (+1 item, in the one
category the base already solves) does not follow its critical
set under ablation and is inside run noise. Per the brief, a
patch is shipped only if the probe supports one; discrimination
without causal leverage is not support. The best-effort
candidate is nevertheless built, placed and fully documented
below (status: NOT DECLARED) so the coordinator may score it on
held-out if a family-2 held-out number is wanted; this worker's
prediction, recorded before any held-out run, is a held-out
delta of ≈ 0. If the coordinator does score it, the pre-stated
R3 reach criterion (CRITERIA.md: dates held-out ≥ base +5 at
dose ≤ 0.1% with retention flat within ±2) is predicted NOT met,
and procedure remains unreached, now bounded from two authored
sides.

## 0. Corrections to the brief, and data discipline

- The T2 diagnostic split contains **60 items** (12 × 5
  categories), not 80; 80 is the T1 diagnostic's size. All R3
  numbers are n=60.
- **No T2 validation split exists.** `batteries/validation.jsonl`
  is T1 arithmetic (200 items); E5's "80/60/60" refers to the
  three tasks' diagnostic sizes. Tuning here is diagnostic-only,
  as the brief's fallback allows.
- The brief's sub-behaviour list (leap years, year rollover)
  does not occur in this battery: all items are set in 2025, a
  non-leap year, within the year, intervals uniformly forward
  (BATTERIES2.md). The sub-behaviours actually present are
  analysed in §1.
- Data discipline: the only battery file opened was
  `batteries/t2_diagnostic.jsonl` (Thor copy md5
  3df0d1ba7ef6569d59382581dd1e652b, identical to the repo's).
  Nothing under any `private/` directory was opened, read,
  copied or scored at any point (held-out/forgetting filenames
  were visible in directory listings during recon only).
- Bench: Thor, `~/wsp-exp16/r3/` (scripts/, results/,
  patched-final/). Python ~/ml/.venv, torch 2.11. Base model
  `~/wsp-exp/models/Qwen3-0.6B` read-only (model.safetensors
  md5 fed58aa6b81fb7e1e6a825af34b3f2dd — matches the md5 R1
  recorded for the pristine base). Scorer: Phase 15 `score.py`
  (Thor harness copy), unmodified; greedy, 96-token cap,
  last-number extraction. Base diagnostic was scored twice with
  identical results (25.0%, per-category identical), and the
  final candidate likewise — the ± movement seen across trials
  is between-configuration, not run jitter, except where noted.

## 1. Baseline: base model on T2 diagnostic — 15/60 = 25.0%

| category | correct | failure structure (from raw outputs) |
|---|---|---|
| weeks_days | 11/12 | The one working procedure: explicit ÷7 with remainder. Sole miss: 97÷7 answered 14 (gold 13). |
| days_between | 2/12 | Cross-month spans collapse: attractor answers 124/126/128 for three different pairs, essay truncation at the 96-token cap; the 2 passes are short within-month spans. |
| weekday_offset | 1/12 | Mod-7 reduction absent: unreduced sums answered directly (11, 17), mapping recited then misapplied, essays truncated. |
| add_days_count | 1/12 | Two variants. (a) Landing-month (1/6): day-by-day enumeration drifts (6 Feb + 60 d → month 2). (b) "Days left in the month after <date>" (0/6): **systematic semantic misread** — the model answers with the NEXT month's length (31/31/30/29/31/31 against golds 13/12/25/25/24/8) on all six items. |
| month_span | 0/12 | Inclusive counting (+1: gold 3 → 4, gold 1 → 3), essay truncation leaving "2025" as the last number (3 items), wild counts (12 for gold 8, twice). |

Headline: every failing category fails as a *procedure* —
the model does not execute day-of-year subtraction, mod-7
reduction, the birthday rule for whole months, or the
remaining-days subtraction — while the one procedure it does
execute (÷7) sits at 91.7%. This matches E5's stage-2 diagnosis
on the stage-1 model and is the boundary family 2 was sent
against.

## 2. Activation probing (diagnostic split only)

Method (`scripts/probe_extract.py`, `probe_extract_mean.py`):
forward passes over the chat-templated prompt (exactly
score.py's template), hooks on every layer's `gate_proj` /
`up_proj`, capturing the MLP neuron signal
act = silu(gate)·up for all 28 × 3072 = 86,016 neurons at two
position definitions: (i) the **last prompt token**
(answer-initiation position, primary) and (ii) **mean-pooled
over prompt tokens** (secondary). Statistics
(`scripts/probe_analyze.py`, `probe_top200.py`): per neuron,
average-rank Mann–Whitney AUC and Cohen's d per contrast;
**null calibration by 300 label permutations per contrast,
taking the maximum AUC across all 86,016 neurons each time** —
a candidate must beat the multiple-comparison ceiling, not 0.5.
The analysis is deterministic (two runs byte-identical).

Process note, recorded plainly: the first analysis version
used unaveraged ranks; activations are tie-heavy (exact
zeros), and with items file-ordered by category that leaks
order into the statistic. It was replaced by the tie-correct
version above and all numbers below are from it. One
intermediate output delivered by the runner was inconsistent
with both versions and was discarded; the canonical analysis
was re-run twice with identical output before any edit was
authored from it.

Contrasts and ceilings (act signal, last-token position):

| contrast | n | best AUC | perm max-AUC mean / p95 / max | reading |
|---|---|---|---|---|
| C1 wrong (45) vs correct (15) | 60 | **0.9615** | 0.799 / 0.865 / 0.910 | Real single-neuron success/failure signal beyond the null. |
| C2 failing cats (48) vs weeks_days (12) | 60 | **1.000** | 0.822 / 0.884 / 0.937 | Category identity is perfectly read out by single neurons. |
| C3 month_span (12) vs weeks_days (12) | 24 | 1.000 | 0.916 / 0.973 / 1.000 | At this n the null itself reaches 1.0; no beyond-null claim. |
| C4 days-left variant (6) vs landing variant (6) | 12 | 1.000 | 1.000 / 1.000 / 1.000 | Null saturates; contrast uninformative at this n. Reported, not used. |

Best gate/up AUCs track act (C1: gate 0.964, up 0.966).

Confounds, stated before the candidate list because they
govern its interpretation:

1. **C1 is category-confounded.** 11 of the 15 correct items
   are weeks_days; within-category correct counts for the
   failing categories are 2/1/1/0, so a within-category
   success contrast is inestimable. C1's "correct-associated"
   neurons may be weeks_days-mode neurons.
2. C2/C3/C4 contrasts are confounded by prompt surface
   (length, template, the mapping sentences). Category
   neurons are prompt-type detectors until an intervention
   proves otherwise.
3. Mean-pooled C1 gives a similar ceiling (best AUC 0.957,
   L11 N1834) with a **largely disjoint neuron set** — the
   readout depends on the position definition, itself a sign
   the signal is distributed/contextual rather than a small
   causal switch.

Top candidates (last-token, C1; full top-200 lists in
results/probe_top200_last.json and probe_top200_mean.json):

- Higher on WRONG items (suppress candidates, group S):
  L26 N2128 (AUC .9615, d +2.31), L12 N787 (.9615, d +3.07),
  L22 N1903 (.957), L15 N717 (.957, d +3.02), L22 N2204 (.957),
  L14 N165 (.953), L15 N2579 (.951), L7 N655 (.950),
  L14 N114 (.950), L3 N1532 (.950).
- Higher on CORRECT items (boost candidates, group B):
  L20 N1902 (AUC .0415, d −2.74), L12 N967 (.0415, d −2.78),
  L16 N2754 (.043), L7 N221 (.043), L13 N1685 (.044),
  L13 N2685 (.047), L5 N2953 (.049), L27 N957 (.049).
- C2 failing-category side (group F): 19 neurons at AUC 1.0
  within the top 30 (e.g. L13 N3071, L4 N1381, L16 N1330).
- C2 weeks_days side (group W): e.g. L21 N2564 (AUC 0.0,
  d −10.0), L15 N806/N808, L15 N786.

## 3. Interventions: eleven trials, no movement

Edit form (all trials): one edit per neuron scaling that
neuron's `down_proj` column (1024 scalars per edit), authored
by `scripts/gen_edits.py` / `gen_edits2.py` **programmatically
from the probe rankings** (thresholds, not hand-picked ids),
applied by `patch.py` from the pristine base. Dose bound
0.1% = 751,632 scalars; the largest trial used 200,704.

| trial | edits (probe source) | scalars | dose | diagnostic | Δ vs base |
|---|---|---|---|---|---|
| base | — | 0 | 0 | **25.0% (15/60)**, scored ×2 identical | — |
| T1 | S ×0.0, 17 (last-token C1) | 17,408 | 0.0023% | 23.3% (14) | −1 |
| T2 | B ×3.0, 13 (last-token C1) | 13,312 | 0.0018% | 23.3% (14) | −1 |
| T5 | F ×0.0, 19 (C2 AUC=1.0) | 19,456 | 0.0026% | 25.0% (15) | 0 |
| T3 | S ×0.0 + B ×3.0, 30 | 30,720 | 0.0041% | 25.0% (15) | 0 |
| T6 | S ×0.5, 17 | 17,408 | 0.0023% | 25.0% (15) | 0 |
| T7 | W ×3.0, 11 (C2) | 11,264 | 0.0015% | 25.0% (15) | 0 |
| T8 | S ×0.0 (96) + B ×3.0 (100), top-200 | 200,704 | 0.0267% | **20.0% (12)** | −3 |
| T9 | S ×0.0 (30) + B ×3.0 (30), mean-pooled C1 | 61,440 | 0.0082% | **26.7% (16)** | +1 |
| T9-S | S only (mean), 30 | 30,720 | 0.0041% | 25.0% (15) | 0 |
| T9-B | B only (mean), 30 | 30,720 | 0.0041% | 25.0% (15) | 0 |

Invariants across all thirteen scorings (base ×2, trials,
ablations): **days_between is 2/12 in every single one**;
month_span is 0–1/12; weekday_offset 1–2/12; add_days_count
0–1/12. All movement, in both directions, is confined to
weeks_days (8–12/12) — the category that was never failing.
The dose-response is negative: the largest intervention (T8,
27× the final candidate's dose) is the worst score, degrading
even the working procedure. That is the signature of
perturbing a readout, not engaging a mechanism.

## 4. Best-effort candidate and the E4-style self-check

The T9 configuration was adopted as the best-effort candidate
(highest diagnostic, mean-pooled probe provenance), rebuilt
from the pristine base by patch.py into
`~/wsp-exp16/r3/patched-final/` (model.safetensors md5
7d7d00262746ba297359b832871de035; receipt: 60 edits, 61,440
scalars changed, 0.00817% — within bound). Re-scored from
patched-final: 26.7% (16/60), identical to the T9 trial,
per-category identical; its entire delta over base is one
weeks_days item (11/12 → 12/12).

Critical-set design: group S (suppress wrong-associated) is
flagged critical — the prediction was that ablating S kills
the effect and ablating an equal count of non-critical (B)
edits does not. Diagnostic self-check:

| configuration | diagnostic |
|---|---|
| full candidate (S+B) | 26.7% (16/60) |
| minus critical S, all (B only) | 25.0% (15/60) |
| minus non-critical B, all (S only) | 25.0% (15/60) |
| minus 15 random S (seed 16046) | 23.3% (14/60) |
| minus 15 random B (seed 16046) | 25.0% (15/60) |
| base | 25.0% (15/60) |

(Note: |B| = |S| = 30, so the equal-count non-critical
ablation is the whole B group — the random-subset form is
the seeded half-ablations.) Verdict: **there is no effect
for the critical set to carry.** Neither group alone does
anything; removing half of either group moves the total by
1–2 items in the already-solved category. The +1 headline is
interaction noise at the single-item level. EXPLANATION.md
records the mechanism claims as contradicted, per protocol.

## 5. Decision

NO PATCH is declared for R3. The probe supports *detectors*,
not *levers*: single MLP neurons at the answer-initiation
position read out success/failure (AUC 0.96 vs null ceiling
0.91) and category (AUC 1.0 vs 0.94), but scaling exactly
those neurons' output columns — suppressing the
failure-associated, boosting the success-associated,
suppressing perfect category detectors, boosting the working
procedure's neurons, at doses spanning 0.0015–0.0267% — moves
no failing diagnostic category in any trial, and larger doses
monotonically hurt. This is the family-2 counterpart of
family 1's stage-2 result (diagnostic +8.3, held-out +0):
two authored sides now bound the same wall — the dates task
fails as procedure (G4 in R2's grading), and neither constant
logit biases nor authored neuron surgery at ≤0.1% installs a
procedure the base does not execute.

Artefacts (this directory): `patch.py` (applier, PATCH-PROTOCOL
shape, supports rows/cols selectors, scale/add/set, --only/
--exclude), `edits.json` (the best-effort candidate, 60 edits,
status NOT DECLARED), `EXPLANATION.md`, `manifest.json`
(edits sha256 a8cdf1c813c1429830d9ac3c928ede9320b32687ead457dae3f37c66c4fc6a43,
61,440 scalars, 0.00817%), `scripts/`, `results/` (baseline ×2,
probe statistics and top-200 rankings for both positions, all
trial and ablation result JSONs with receipts).

## 6. Coordinator scoring commands (exact)

Rebuild the best-effort candidate from the pristine base
(optional; `~/wsp-exp16/r3/patched-final/` already exists):

```
cd ~/wsp-exp16/r3
~/ml/.venv/bin/python scripts/patch.py --edits ~/jacquard-p16-r3/experiments/wsp2/r3/edits.json \
  --model ~/wsp-exp/models/Qwen3-0.6B --out ~/wsp-exp16/r3/patched-final
```

Held-out + task-retention scoring (Phase 15 scorer on the
Thor; split names: T2 = `t2_heldout`, T1 = `heldout`,
T3 = `t3_heldout`). Base first, then candidate:

```
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp/models/Qwen3-0.6B \
  --split t2_heldout --out ~/wsp-exp16/r3/results/coord_base_t2_heldout.json
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp16/r3/patched-final \
  --split t2_heldout --out ~/wsp-exp16/r3/results/coord_besteffort_t2_heldout.json
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp/models/Qwen3-0.6B \
  --split heldout --out ~/wsp-exp16/r3/results/coord_base_t1_heldout.json
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp16/r3/patched-final \
  --split heldout --out ~/wsp-exp16/r3/results/coord_besteffort_t1_heldout.json
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp/models/Qwen3-0.6B \
  --split t3_heldout --out ~/wsp-exp16/r3/results/coord_base_t3_heldout.json
~/ml/.venv/bin/python ~/wsp-exp/harness/score.py --model ~/wsp-exp16/r3/patched-final \
  --split t3_heldout --out ~/wsp-exp16/r3/results/coord_besteffort_t3_heldout.json
```

Criterion check (CRITERIA.md, R3, unchanged): family 2
REACHES iff candidate t2_heldout ≥ base t2_heldout + 5 points
(E5 record: base 30.8%) with T1/T3 held-out each within ±2
points of base. This worker's prediction: not reached
(candidate held-out ≈ base ± noise).

## 7. Process notes

- Oracle disk was at 100% (26 MB free) on arrival; the clone
  was made with `git clone --local` from the existing Phase 16
  clone plus a delta fetch of origin/main (tip 2e1e80b), and
  only text artefacts were committed. No foreign files were
  deleted or moved.
- GPU sharing: all Thor runs were single-model, ≤ ~70 s each;
  no foreign process was touched. Total Thor wall time ≈ 25
  minutes including the discarded first analysis.
- The probe tensors (62 MB × 2) and trial edits stay on the
  Thor under ~/wsp-exp16/r3/; only statistics, rankings,
  scripts, results JSONs and the patch artefacts are in git.
