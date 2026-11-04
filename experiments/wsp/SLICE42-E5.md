# Slice 42 (part 2) — E5: successive-task stress, patch chain vs LoRA chain

Three tasks in sequence — T1 arithmetic, T2 date/interval
arithmetic, T3 unit conversion — applied to the same base
(Qwen3-0.6B). Each stage sees only its own task's diagnostic
split (80/60/60 items). After every stage, ALL tasks are
scored on held-out (T1 n=200, T2/T3 n=120) plus the three
forgetting batteries. All numbers coordinator-run.

## Held-out trajectories

Authored patch chain:
| task | base | +stage 1 | +stage 2 | +stage 3 |
|---|---|---|---|---|
| T1 arithmetic | 80.5 | 85.0 | 85.5 | 85.5 |
| T2 dates | 30.8 | 26.7 | 23.3 | 23.3 |
| T3 units | 72.5 | 70.8 | 70.8 | 70.8 |
| forget_instr / fact / prose NLL | 81/85/4.069 | 81/85/4.074 | 81/85/4.074 | 81/85/4.074 |

LoRA chain (same recipe as E3, retrained per stage on the
merged previous stage):
| task | base | +stage 1 | +stage 2 | +stage 3 |
|---|---|---|---|---|
| T1 arithmetic | 80.5 | 48.0 | 56.0 | 59.0 |
| T2 dates | 30.8 | 9.2 | 20.0 | 19.2 |
| T3 units | 72.5 | 32.5 | 42.5 | 63.3 |
| forget_instr / fact / prose NLL | 81/85/4.069 | 84/87/3.991 | 87/85/3.998 | 85/83/3.979 |

## What the curves say

The no-catastrophic-forgetting claim for authored patches
HOLDS in the sense measured — with two honest qualifications:

1. Retention is real. The stage-1 gain survived stages 2
   and 3 untouched (T1 heldout 85.0 -> 85.5); the forgetting
   batteries never moved at any stage. No patch stage
   destroyed anything a previous stage had built.
2. But patches are not free, and their yield is bounded by
   failure TYPE. Stage 1's digit bias taxed T2 before T2
   was targeted (30.8 -> 26.7: date answers need the verbal
   scaffolding the bias suppresses). Stage 2 (T2 target)
   gained +8.3 on its diagnostic and ZERO on held-out — its
   own author predicted the template-luck risk in advance
   and the held-out confirmed it. Stage 3 (T3 target) is an
   evidenced negative: T3's failures are 85% factor/direction
   knowledge errors (x12 vs x144, x vs divide), and 13
   trialled bias variants never beat baseline on their own
   tuning split — a constant logit bias arbitrates surface
   competitions; it cannot supply a fact that must win in
   one context and lose in another. The shipped stage-3
   patch is control-only and exactly inert, as predicted.

The gradient chain shows the opposite signature on every
axis. Interference is immediate and catastrophic: stage 1
alone — trained only on T1 — cut T2 to 9.2 and T3 to 32.5.
Later stages partially recover the wreckage (T3 climbs
back to 63.3 by its own stage) but no task ever reaches
the never-trained base, including each task at the moment
it was trained on (T3 after T3 training: 63.3 vs base
72.5). Sequential bare-answer LoRA at this recipe is a
strictly dominated strategy on this bench.

A measurement finding hides in the forgetting rows: the
generic forgetting batteries (facts, instructions, prose
NLL) stayed healthy for BOTH chains at every stage — for
the LoRA chain they IMPROVED while its task capabilities
were being destroyed. Catastrophic forgetting here is
capability-shaped, and generic probes do not see it. Any
future "no forgetting" claim — for patches or anything
else — should be required to show task-held-out curves,
not just generic batteries. (The patch chain's clean
forgetting rows are corroborated by its task curves; on
their own they would prove nothing.)

## The yield curve of authored patching, across the phase

Stage 1 (format failure): +4.5 held-out, retained forever.
Stage 2 (procedure failure): +0 held-out.
Stage 3 (knowledge failure): +0, evidenced.
The patch form's power is real and narrow: it fixes how a
model deploys what it already knows. It does not install
procedures or facts — at 0.004-0.006% of parameters, with
constant authored biases, nothing in this phase could.
