# Phase 16 findings — the boundary, mapped; the two open doors, tested

Programme: Jacquard Phase 16 (slices 44-46). Charter:
BUILD-BRIEF-PHASE16.md (Casey, 2026-11-03, "R&d"). Phase 15
established authored weight patching as a behaviour-deployment
instrument with a boundary at procedure, facts, and unseparated
relations. Phase 16 mapped that boundary with a reusable
instrument, autopsied Phase 15's one ambiguous negative, and
tested the two doors Phase 15 left open: a second patch family
against procedure, and a second signal-chain joint. Every
criterion below was pre-stated and hash-bound into the
governance log before the test it governs ran
(experiments/wsp2/CRITERIA.md).

## The headline table

| test | pre-stated criterion | measured outcome | door |
|---|---|---|---|
| R1 E8 transfer autopsy | transfer = canonicalised held-out (a) gap >= +10 AND >= 8 non-ALLOW AND (b) not below base | gap exactly 0.0; non-ALLOW 0/53; patched item-identical to base AGAIN | CLOSED — representation claim |
| R2 profile, Qwen3-0.6B | yield = held-out >= +3 at dose <= 0.1%, retention flat within +-2 | yields at G1 only; G2 +42.5 denied by the retention clause alone | boundary after G1 |
| R2 profile, LFM2-1.2B | same | yields at G1 only; G2 +41.7 denied by the retention clause alone | boundary after G1, different reasons |
| R3 neuron surgery (family 2) | dates held-out >= base +5 at dose <= 0.1%, retention flat | no patch declared; undeclared candidate held-out 28.3 vs base 30.8 | CLOSED — from a second authored side |
| R4 second joint (panic dial) | round 1: held-out >= better incumbent + 10, no class traded away | 50.8 vs incumbents 32.5 (student) / 15.0 (dial); adopted. Round 2: 49.2, DENIED | OPEN — generality confirmed |

## R1 — the format eras are acquitted; the representation is not

Phase 15's E8 negative had two candidate causes: the record's
format eras, or the student's representations. Slice 44
re-expressed the held-out decisions in the diagnostic era's
canonical format under a mechanical verifier (165/165 items:
every content field identical, only rendering changed) and
re-scored the preserved patched student. It is item-identical
to the unpatched base a second time — 53/53 ALLOW, the
operator-agreement gap exactly 0.0 against a +10 bar. The
reverse direction (diagnostic in held-out-era format) costs
the patch one net item (96.4 -> 95.5): the patch is not
format-fragile; the held-out failure is not a rendering
failure. The probes then name what does not transfer, at
relation level: same-exclusive-seat contention vs legal
overlaps, AUC 0.444 (the incumbent-wrong trio projects BELOW
legal overlaps); the gpu-windows DENY relation vs gpu ALLOW,
AUC 0.500 on the deny direction and 0.000 — anti-separated —
on the hold direction; the one gpu HOLD item sits inside the
ALLOW cloud on both diagnostic directions. The custom
decision model's preconditions, as Phase 15 measured them,
fail on the representation side, not the curriculum side.
The door closes with the relations named. (The autopsy also
corrects Phase 15's own phrasing: renderer drift between
eras was overstated — 37 of 53 held-out items already arrive
in diagnostic-era formats. Recorded as defect D1 in
R1-AUTOPSY.md.)

## R2 — the boundary map, and the clause that drew it

The instrument (experiments/wsp2/profile/: graded batteries,
1,740 items, independently reviewed before patching;
task-held-out retention curves throughout, no generic
forgetting batteries) profiled two students from different
families. The maps:

Qwen3-0.6B — G1 format/completion YIELDS (+30.0 held-out,
dose 0.008%). G2 framing posts the map's largest own-grade
gain (+42.5) and is NO YIELD: its patch spends G1's held-out
by -7.5 through shared Yes/No rows. G3 readout: the shipped
patch does not transfer (-0.83) and breaches G2 retention
(-9.2). G4 procedure, G5 facts, G6 unseparated relation: no
patch authored, each on probe evidence (G5's +4.0 and other
pass-through movements are chain side-effects and earn
nothing).

LFM2-1.2B — the mirror image at baseline (strong where Qwen
is weak: G5 81.0 vs 18.0; weak where Qwen is degenerate: G6
0.0, a constant first-token HOLD under strict scoring), and
the same boundary: G1 YIELDS (+31.7, dose 0.001%). G2 again
posts the largest gain (+41.7) and is again denied SOLELY by
retention (-13.3 on G1). G3 was never shipped (two attempts
below the chained base) yet shows +24.2 of pure chain
side-effect — recorded, uncredited. G4-G6: no patch, probe
evidence.

Three conclusions the map supports:

1. The boundary by failure TYPE replicates across families:
   format/completion yields in both models; procedure, facts
   and unseparated relations yield in neither — G6 is
   non-separated in both geometries (class-mean distance
   0.39 against a mean norm of 167.5 in Qwen; 0.76 against
   98.4 in LFM2).
2. The retention clause is load-bearing, not a formality.
   Judged per-patch, G2 would be the profile's biggest
   success on both models; judged in chain — the only way
   patches are ever actually deployed — it is a transfer
   from G1, not a gain. Phase 15's E5 chain kept retention
   because its stages pulled disjoint levers; the profile's
   early grades share one readout surface (Yes/No), and the
   tax appears immediately. A patchability claim without a
   retention curve is, as of this map, an incomplete claim.
3. Chained side-effects are large in both directions
   (LFM2 G3 +24.2 uncredited; Qwen G3 -9.2 charged to G3's
   step). The instrument now measures them by construction;
   any future profile that reports only own-grade deltas is
   hiding its largest numbers.

## R3 — discrimination is not leverage

Family 2 (authored edits to probe-identified MLP neurons)
was tested against the dates procedure task, family 1's
cleanest zero. The probes were not the problem: single
neurons discriminate wrong-vs-correct at AUC 0.9615 and
failing-category-vs-solved at AUC 1.000, both beyond
300-permutation null ceilings. Eleven intervention trials on
exactly those neurons then moved nothing that was failing —
days_between scored 2/12 in all thirteen scorings, every
gain confined to the already-solved category, dose-response
negative (the largest dose scored worst), and the E4
self-check contradicted the author's mechanism claims. No
patch was declared. The coordinator scored the undeclared
best-effort candidate on held-out anyway, to close the
criterion on its own terms: 28.3 against base 30.8 and a
35.8 bar — the author's recorded prediction, confirmed.
The finding generalises past this task: in this model the
neurons that DETECT a procedure state are not levers that
DRIVE it; the procedure is distributed across the
computation in a way single-neuron authored edits do not
reach. Procedure is now bounded from two authored sides —
readout geometry (family 1) and neuron intervention
(family 2). Gradient training is not a third side; it is
not authored, and its record (Phase 15: catastrophic,
unreadable) stands.

## R4 — the second joint: generality, priced

The E7 inventory of signal-chain held one joint; the dial's
home, elephant's DialBank, held more. The panic dial (room
alarm state: calm / alarmed / stampede) is the same spine
pattern — lexicon counting, equal weights — with a different
judgement type, and the same incumbent shape of failure: the
dial never once predicts stampede (its readings top out at
0.635 against a 2/3 band) and scores 15.0% held-out; the
zero-shot student is a single-attractor "alarmed" machine at
32.5%. Round 1's family-1 readout patch (6,144 scalars,
0.00082%): diagnostic 30.0 -> 78.3, held-out 50.8 with all
three classes alive — ADOPTED. Round 2 (a shrinkage
refinement; diagnostic deliberately traded down to 72.5):
held-out 49.2, stampede below its floor — DENIED; round 1
stands. The rhyme with joint 1 is exact in structure and
opposite in direction: joint 1's round 2 overfit upward,
joint 2's round 2 shrank — neither added transfer. What
round 1 installs is what this family transfers; refinements
in either direction spend it. Round 2's durable yield is
metrology: on this tied-embedding student the direction dose
has a measured ceiling (0.20) set by input-coupling noise
growing with delta norm, and the dial's modality blind spot
(scheduled-drill notices) is a representation limit even
leave-one-out.

Marginal cost of joint N+1 against joint N, as chartered:
joint 2 was counted live — battery construction ~12 min,
round 1 ~12 min, round 2 ~16 min of worker time, 0 teacher
calls at every step, coordinator scoring two ~15-second
runs, 2 governance proposals and 2 decisions. Joint 1's
figures cannot be separated from Phase 15's record (it ran
inside a multi-experiment phase that also built the harness,
the protocol and the governance driver), and are labelled
estimated for exactly that reason. The honest statement of
the compounding claim: the second joint cost roughly an
hour of agent time end to end BECAUSE the first joint paid
the fixed costs — battery discipline, patch protocol,
governance rails, scoring harness all reused unchanged.
Generality is cheap precisely where the record said it
would be: in the marginal joint, not the first.

## Governance, whole phase

Canonical log (experiments/wsp/governance/kernel.jsonl):
195 -> 279 entries. Pre-stated criteria for R1-R4 and the
R4 amendment hash-bound before their tests; verdict evidence
for R1 and R3; two deployment proposals (R4 rounds 1-2):
1 approved, 1 denied. The profile's ratification (5
proposals, 5 decisions — 2 approve, 3 deny — and 12 evidence
entries, labelled ratification, not prospective gating) ran
in the grader's clone against the 237-entry state and is
preserved verbatim as its own valid chain at
experiments/wsp2/profile/ratification-kernel.jsonl (398
entries; see RATIFICATION-NOTE.md for why the chains were
not force-merged). No patched copy was adopted into any
serving role; that remains Casey's call, as chartered.

## Limits and defects, stated

One bench (Thor), one patch family home plus one neuron
family, students at 0.6B and 1.2B (the second present only
as a GGUF, loaded via the documented route). The profile's
G6 grade carries the reviewer's wording limit (start
offsets bimodal; near-boundary behaviour unmeasured). The
R4 battery is construction-labelled, as E7's was. Process
defects of this phase, in its own record: the coordinator
committed unresolved merge markers into the builder's log
in 1feb4b1 (fixed by union in bce1db6; the fix commit names
the error); the Qwen G1 patch took four builds against a
two-candidate bound (patcher-declared deviation, recorded
in PATCHING-RECORD.md; its yield was judged on held-out
like every other grade); the governance log forked between
the coordinator's clone and the grader's and was preserved
as two valid chains rather than rewritten. The seat pool
was not used — Pi's crash, Kimi's quota and ZCode's
saturation from Phase 15 were not re-litigated; all roles
were filled by coordinator-spawned workers with the
charter's separations preserved exactly (builder, reviewer,
patcher, grader distinct at every step), as the brief
provides.
