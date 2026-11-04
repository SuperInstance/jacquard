# Slice 43 — Phase 15 findings: weight-space programming, measured

Programme: Jacquard Phase 15 (slices 41-43). Bench: one
small model (Qwen3-0.6B, 751,632,384 parameters, tied
embeddings) on one Jetson AGX Thor; every experiment on
copies; every verdict number from the phase's own harness
run by the coordinator; every patch artefact, battery,
and governance record in this tree. The claim that
chartered the phase (a frontier model editing 0.016% of
a small model's weights for up-to-6x benchmark gains, no
gradient descent) was graded blog-post evidence at
charter; this phase was built to be able to say no. In
places it does. In places it says yes, with boundaries
it can point to.

## The headline table

| experiment | result |
|---|---|
| E1 replication | held-out 80.5 -> 85.0 (+4.5), forgetting unmoved |
| E4 falsification | CONFIRMED: minus-critical = base exactly; minus-random = full exactly |
| E3 fluid (context) | held-out 78.5 (below base); forget_fact 85 -> 9 |
| E3 gradient (LoRA) | held-out 48.0; its training amputated the CoT scaffold |
| E3 yang (patch v1) | held-out 85.0, forgetting identical to base |
| E5 patch chain | gains retained across 3 tasks; yield zero on procedure & knowledge tasks |
| E5 LoRA chain | every task ends below the never-trained base; interference catastrophic from stage 1 |
| E2 lifecycle | eval -> shadow -> canary -> adopt -> rollback, bit-for-bit, 4 decisions |
| E6 loop | 80.5 -> 85.5 -> 87.5 -> (round 3 denied); closed 35.9% of the teacher gap, then plateaued on evidence |
| E7 joint | patched specialist held-out 84.2% vs incumbent joint 46.7% (mixed 75% vs 7.5%); round 2 refinement rejected (divergence) |
| E8 decision model | diagnostic (a) 96.4 / (b) 93.3; held-out item-identical to base; incumbent-wrong trio learned as ALLOW; adoption denied |

## What authored patching is, as measured here

A behaviour-deployment instrument. It fixes how a model
deploys what it already knows:

- Format and completion failures are its home ground.
  Verbose essays truncating at the token cap, answers
  landing in the wrong sentence frame, a missing class
  basin in a classifier: all harvested, repeatedly, at
  0.003-0.006% of parameters, with forgetting batteries
  never moving in any patch chain at any stage.
- Where the base representation already separates the
  target classes, a patch can install the readout: E7's
  classes were linearly separated (Euclidean centroid
  form) and 6,144 authored scalars turned a 41.7%
  student into an 84.2% joint.
- Its yield is bounded by failure TYPE, and the boundary
  was hit from three directions independently: procedure
  failures (E5 dates: diagnostic +8.3, held-out +0),
  factor-knowledge failures (E5 units: 13 variants, zero),
  and relations the representation does not separate
  (E8's same-seat contention: geometrically
  indistinguishable from legal overlaps). In each case
  the correct deliverable was an evidenced negative, and
  each negative is in this tree with its trial battery.

The 6x headline did not reproduce — and the phase can
say precisely why that is not a refutation: the source's
failure mass was evidently capability-shaped at its
scale; ours, measured item by item, was behaviour-shaped
at the top (worth +4.5 to +7 points) and capability-
shaped underneath (worth zero to this method). A patch
cannot install arithmetic reliability a model does not
have. It can stop the model from wasting the reliability
it does have — that, quantified, is the method's power
on this bench.

## The three poles, as an engineering comparison

Casey's frame — liquid yin, authored yang — survived
measurement as a taxonomy of ARTEFACTS:

- Fluid (context adaptation): no weight artefact at all.
  Its one artefact is enumerable text, but its EFFECT is
  not: the same prompt package that fixed chains
  collapsed unit_price to 12% and fact recall to 9%
  (the model answered "47" to every capital). Nobody
  predicted the collateral; nothing in the artefact lets
  you ablate it. Global instrument, global side effects.
- Gradient (LoRA): an artefact, but unreadable — 6.4M
  scalars whose honest summary was "the loss went down,"
  and the loss going down WAS the failure (bare-answer
  training amputated the reasoning scaffold; held-out
  48.0). Chained across tasks it corroded everything,
  including the tasks it trained on, while generic
  forgetting probes stayed green.
- Yang (authored patches): the only pole whose artefact
  is simultaneously the intervention, its explanation,
  and its own undo. Every yang claim in this phase was
  subjected to E4 discipline — ablate the claimed-
  critical edits and the effect vanishes to the item;
  ablate random edits and it persists; restore and it
  returns. Explanations that cannot survive ablation
  were not shipped as explanations.

## The loop, and where the GAN analogy ends

E6 ran Casey's teacher-student loop on governed rails:
fresh round batteries as the judging function, a teacher
authoring patches from diagnosed failures, held-out
sealed from every teacher, adoption decided from the
record. It closed 35.9% of the gap to the teacher
(80.5 -> 87.5) in two adopted rounds — digit-boost, then
opener suppression, a lever different in kind — and then
stopped on evidence: round 3's six-lever falsification
battery found the reachable mass exhausted, its adoption
was denied in the log, and the student never moved.

Where the analogy holds: a judging function, a generator
of students, iterated selection pressure, diminishing
returns to an asymptote. Where it breaks, and the break
is the point: there is no gradient anywhere — the teacher
authors discrete, human-readable edits from a failure
taxonomy, not differentiable feedback; the loop's state
is not ephemeral weights but a ledger of sealed, scored,
reversible commits in which REJECTIONS are first-class
artefacts (three of this phase's ten deployment proposals
were denied, each with its evidence attached); and the
judge cannot be fooled by the generator because held-out
is sealed from it — a GAN has no equivalent of held-out
discipline. E7 round 2 showed what the discipline is
for: diagnostic +6.7, held-out -4.2, a class silently
traded away — an unguarded loop ships that patch. This
one has its refusal on record. A distillation loop with
a ledger, then: the ledger is not bookkeeping, it is the
mechanism that makes the loop safe to run unattended.

## Governance cost, whole phase

One kernel log (`governance/kernel.jsonl`, 195 entries):
10 deployment proposals — 7 approved, 3 denied — plus
evidence submissions at every gate, all hash-bound, all
replayable. E2's full lifecycle cost 4 decisions and
~25 minutes dominated by the measurement runs its
evidence required; the kernel interactions are seconds.
The record gates; the models only ever advised it.

## Limits of this phase, stated

One model at one scale (0.6B); one patch family home
(tied-embedding rows, label rows, mean-direction
geometry); LoRA at one pre-registered recipe; the fluid
pole at one package; E7's battery synthetic by
construction; E8's held-out small (n=53) and ALLOW-heavy
with a correctness subset of 14. Teacher predictions
were calibrated on arithmetic rounds (+4/+5.0, +3/+2.0,
0/0) and miscalibrated on refinement rounds (E7 round 2
predicted +3..+7, measured -4.2). Nothing here measures
the method at the source claim's scale, and the findings
do not pretend to. What generalises is the discipline,
not the point estimates: diagnose the failure type
before choosing the instrument; record the prediction
before the score; ablate the explanation before
believing it; seal the held-out set; let the record —
never the proposer — decide adoption.
