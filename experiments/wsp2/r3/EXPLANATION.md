# EXPLANATION — Jacquard Phase 16, R3 (family 2: authored neuron surgery)

Student: Qwen/Qwen3-0.6B (bf16, 28 layers, hidden 1024,
intermediate 3072, 751,632,384 parameters). Artefacts:
`patch.py` + `edits.json` in this directory; built model at
~/wsp-exp16/r3/patched-final/ on the Thor.

**Status: NO PATCH DECLARED.** The edits in edits.json are the
best-effort candidate (trial T9): 60 edits, 61,440 scalars
changed = 0.00817% of parameters (bound 0.1% = 751,632).
Diagnostic (T2, n=60): base 25.0% → candidate 26.7%, the
entire delta being one item in weeks_days, the category the
base already solves (11/12 → 12/12). Every claim below was
tested and the outcome is recorded with it, per protocol:
mechanism stories the ablation contradicts are recorded as
contradicted, not edited away.

## The edit form

Every edit scales one column of one layer's
`mlp.down_proj.weight` — i.e. it scales the output
contribution of exactly one MLP neuron (act = silu(gate)·up,
contribution = act × down_proj[:, neuron]) at every token
position. Scale 0.0 removes the neuron's contribution;
scale 3.0 triples it. All neuron choices were generated
programmatically from the probe rankings (threshold rules in
scripts/gen_edits2.py over results/probe_top200_mean.json);
no neuron was hand-picked.

## Group S — suppress wrong-associated neurons (30 edits, CRITICAL)

Which weights: down_proj columns of the 30 neurons whose
mean-pooled MLP activation most strongly discriminates items
the base gets WRONG from items it gets right on the T2
diagnostic split (contrast C1, AUC ≥ 0.90 side; top: L11
N1834 AUC .957, L16 N1298 .953, L27 N2318 .950). C1's best
AUC (0.9615 last-token) exceeds the 300-permutation
max-across-86,016-neurons null ceiling (max 0.910), so the
discrimination itself is real.

Stated mechanism claim: these neurons carry a
failure-associated mode at the answer-initiation region;
removing their contribution should release the failing
categories (days_between, weekday_offset, add_days_count,
month_span) toward the model's latent correct procedure.

**Outcome: CONTRADICTED.** S alone scores exactly base
(25.0%); no failing category moves under S in any trial
(last-token or mean-pooled provenance, scale 0.0 or 0.5,
17–96 neurons). The discrimination is a readout, not a lever.

## Group B — boost correct-associated neurons (30 edits, non-critical)

Which weights: down_proj columns of the 30 neurons most
associated with CORRECT items (C1, AUC ≤ 0.10 side; top:
L10 N512 AUC .044, L12 N2357 .044, L15 N2482 .046), scaled
×3.0.

Stated mechanism claim: amplifying the success-associated
mode should bias generation toward whatever the model does
when it succeeds (notably the explicit ÷7 procedure of
weeks_days).

**Outcome: CONTRADICTED.** B alone scores exactly base
(25.0%); the S+B combination's +1 item does not appear with
either group alone and does not survive half-ablations as a
critical-set effect (see R3-PATCH.md §4). Note the recorded
confound: 11/15 correct diagnostic items are weeks_days, so
"correct-associated" may mean "weeks_days-mode" — consistent
with the only movement ever observed being inside
weeks_days itself.

## The critical-flag prediction, as tested

Prediction registered in the edit design: ablating the
critical set (S) kills the candidate's diagnostic effect;
ablating an equal count of non-critical edits (B) does not.
Result: the prediction is VOID, not confirmed — there is no
effect to kill. Full candidate 16/60; minus-S 15/60;
minus-B 15/60; minus a seeded random half of S 14/60; minus
a seeded random half of B 15/60; base 15/60 (scored twice,
identical). All variation is single-item movement inside
weeks_days.

## What this patch provably does not do

It does not install day-of-year subtraction, mod-7 reduction,
the whole-month birthday rule, or the remaining-days
subtraction — in eleven configurations, including a
200,704-scalar dose (0.0267%) that scored *below* base
(20.0%). Together with family 1's stage-2 result, this is
the second authored bound on the same procedure wall.
