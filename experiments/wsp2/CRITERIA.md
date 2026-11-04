# Phase 16 — pre-stated criteria (recorded before any test runs)

Charter: BUILD-BRIEF-PHASE16.md (Casey, 2026-11-03, "R&d").
These criteria were written and hash-bound into the governance
log (experiments/wsp/governance/kernel.jsonl, stages
p16-r1-criterion .. p16-r4-criterion) BEFORE the artefacts they
govern were touched. A criterion changed after its test runs is
a new criterion and must be recorded as one.

## R1 — E8 transfer autopsy: discrimination criterion

Question: was E8 round 1's zero held-out transfer caused by
(a) the record's FORMAT ERAS (held-out items arrive in surface
formats the diagnostic era never showed), or (b) the student's
representations not carrying the operator's weighting?

Test: re-express the E8 held-out set (n=53) in the diagnostic
era's canonical format — content preserved, format normalised
— and re-express the diagnostic set (n=112) in a held-out-era
format. Re-score the PRESERVED Phase 15 round-1 patched student
and the unpatched base on all re-expressed sets, dual scores
(a) agreement-with-operator and (b) agreement-with-correctness
always separate.

TRANSFER APPEARS iff, on canonicalised held-out, the patched
student beats the unpatched base by >= +10 points on (a) AND
answers non-ALLOW on >= 8 of 53 items AND (b) on the
correctness subset (n=14) is not below base. (Phase 15 baseline:
patched == base item-identical, gap exactly 0; base rates
(a) 88.7 / (b) 64.3.)

If transfer appears: ONE governed patch round on canonicalised
diagnostic data only. Adoption bar for that round, on
canonicalised held-out: (b) >= base (b) + 15 points AND
non-ALLOW answers >= 15% of items AND (a) not below base (a) - 5.

If transfer does not appear: run the representation probes on
the canonicalised data (same-seat contention trio vs legal
overlaps; projection AUC and margins, E8 probe as template).
The door closes as a REPRESENTATION claim, with the failing
relations named. No further patch round is run.

## R2 — patchability profile: grading and yield definitions

Failure-type grades, in boundary order: G1 format/completion,
G2 framing, G3 readout (representation separates), G4
procedure, G5 factor-knowledge, G6 unseparated relation.
Every grade carries diagnostic / validation / held-out splits
and TASK-HELD-OUT retention curves (retention of previously
profiled tasks measured after each grade's patch — generic
forgetting batteries are not used as evidence of retention,
per Phase 15's methodological finding).

A grade YIELDS on a model iff its patch improves held-out by
>= +3 points at dose <= 0.1% of parameters with retention
curves flat within +-2 points on previously profiled tasks.
Below that: NO YIELD. Doses, held-out deltas and governance
decisions are reported per grade per model; the boundary map
is the table of yields.

Battery acceptance: an independent reviewer (not the builder)
audits for label errors, split leakage, matcher defects and
impossible items BEFORE any patching; blocking defects found
are fixed and the audit re-run, as in Phase 15.

## R3 — authored neuron surgery: reach criterion

Family 2 = authored edits confined to probe-identified MLP
neurons / gates (activation probing on the diagnostic split
only; edits enumerated, <= 0.1% of parameters, reversible,
PATCH-PROTOCOL shape). Target: the dates procedure task
(Phase 15, family 1: diagnostic +8.3, held-out +0).

Family 2 REACHES procedure iff the dates held-out improves
>= +5 points over the unpatched base at dose <= 0.1% with
retention flat within +-2 points. Anything less: procedure
remains unreached, now bounded from two authored sides
(gradient training is not a third side — it is not authored,
and its record stands).

## R4 — second joint: protocol and substitution

The E7 inventory holds exactly ONE real joint in signal-chain
(the dial weighting in signal_chain_dial.py::_score); the Rust
DSP chain is pure functions with no judgement joint. R4 is
therefore a NAMED SUBSTITUTION, recorded as such: the
gpu-queue downstream-use judgement in the fleet's own
tooling — given a submitted job's record, will its output be
consumed? Spine (gpuq queue machinery) hard; incumbent joint
= (i) majority-class base rate and (ii) the consumption-policy
v2 class rule. Judgement type differs from E7 (prospective
outcome prediction, not text-spectrum classification).
Dataset precondition: >= 150 labelled jobs, minority class
>= 25%, time split possible; if the records cannot support
that, the substitution fails on data and is reported as such
before any patching.

Protocol = E7's: incumbent and student baselines, at most
two governed patch rounds, divergence (diagnostic up,
held-out down) denies. Success bar = round-1 form: held-out
beats the better incumbent by >= +10 points with no class
traded away (minority-class recall not below incumbent's).
Marginal cost accounting: joint N+1 vs joint N in coordinator
wall time, worker wall time, teacher calls and governance
decisions — counted live for joint 2; joint 1 figures taken
from the Phase 15 record and labelled counted vs estimated.
