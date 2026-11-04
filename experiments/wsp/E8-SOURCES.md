# E8 curriculum sources — inventoried 2026-11-04 (build at slice 43)

The custom-decision-model battery is curated from Jacquard's
own record. Sources, all in the jacquard repo (this clone) or
the board repo:

- docs/shadow-trial-2026-11-02.md + tools/shadow_trial.py —
  the shadow trial: 52 decisions, advisor 46/52 (88%), and
  the 3 cases where the INCUMBENT (operator-side default)
  was wrong. These 3 anchor the correctness-split scoring.
- tools/jev_experiment.py — the stock advisor experiment:
  11 cases, 10/11 agreement; the miss flattened HOLD into
  DENY (a weighting failure — the E8 target behaviour).
- docs/proof-run-2026-11-02.md, docs/proof-run-2-2026-11-02.md,
  docs/slice*-live-report.md — recorded proposal/decision
  pairs from the proof and live-window runs.
- The gpu-queue log (live on the Thor; replay tool
  tools/replay_gpu_queue.py) — hundreds of submit/decide/
  dispatch entries with outcomes; consumption-policy v2
  (docs/slice27-consumption-policy-v2.md) repriced real
  jobs — decisions with measurable right/wrong after the
  fact (consumed vs churned).
- ~/agent-inbox/schedule/*.md + its git history — booking
  decisions (grants, conflicts, the Phase 11 tie) with
  timestamps; the git history provides the time split for
  held-out = later decisions.

Battery shape (to finalise at curation): each item renders
a recorded decision context as a prompt (producer, effect
shape, resource, queue state, policy facts) with the
recorded outcome as gold (ALLOW / HOLD / DENY). Splits by
TIME: curation/diagnostic from earlier records, held-out
from later ones, disjoint by log position. Two scores per
PLAN.md: agreement-with-operator, and agreement-with-
correctness on the subset where the record shows the
operator/incumbent was wrong (shadow trial's 3 + gpu
consumption outcomes where the recorded decision's result
is measurable). Baselines: 10/11 stock experiment, 88%
shadow trial — the custom model must beat them honestly
or the E8 record says it did not.
