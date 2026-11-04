# R4 Round 2 — DESIGN (stated BEFORE building the final patch)

Patcher record, 2026-11-04. Joint: elephant PanicDial
(calm / alarmed / stampede), student Qwen3-0.6B, family 1.
Round 1 is adopted and stands unless this round beats it on
the coordinators held-out under the pre-stated bar:
held-out > 50.8 overall AND no class recall more than
5 points below round 1s (calm 27.5 / alarmed 72.5 /
stampede 52.5). Diagnostic split only used throughout;
held-out never read, listed, or scored by this patcher.
Teacher calls: 0.

## What round 1s held-out verdict says (aggregates only)

Diagnostic 78.3 -> held-out 50.8. Per class: calm
62.5 -> 27.5 (27/40 held-out calm items answered alarmed),
stampede 85.0 -> 52.5 (17/40 answered alarmed), alarmed
87.5 -> 72.5. The failure is one-directional: in the
unseen world the alarmed attractor re-asserts itself
against both other classes. The components of round 1
that are fitted constants or base-model priors are the
suspects; the per-item direction signal is the component
that should travel, because it encodes the rooms alarm
semantics rather than this worlds surface balance.

## Diagnostic probes run for this round (diagnostic only)

1. Leave-one-out nearest-centroid on base hidden states:
   85.8% (calm 75.0 / alarmed 95.0 / stampede 87.5).
   Per subtype: drill_notice 0/4 even under LOO centroid
   — its hidden states sit nearer other classes means;
   that is a REPRESENTATION limit at the final hidden
   state for scheduled-drill modality, not a readout
   margin problem, and this round does NOT chase it with
   subtype-specific edits. negated_alarm 3/5 LOO
   (partially separable), work_routine 3/7,
   technical_cascade 3/6.
2. Split-half direction stability: cos(D_half1, D_half2)
   = 0.745 calm / 0.735 alarmed / 0.824 stampede. The
   class-mean directions carry real sampling noise at
   n=40/class; a denoising variant was cross-tested
   (below) and not adopted (neutral at the chosen
   operating point).
3. Cross-fitted selection (the anti-E7 instrument):
   5-fold stratified partition of diagnostic; ALL
   geometry and sim calibration refit on the 96 training
   items of each fold, scored on the 24 held out from
   fitting. Fixed-hidden-state simulation (gamma_sim
   only; gamma_full/resid cancel a real-model coupling
   that does not exist in simulation). Results:
     pure centroid (cross-fitted)   82.5  (67.5/97.5/82.5)
     round-1 recipe s=0.10          82.5  (82.5/75.0/90.0)
     s=0.05 / 0.15 / 0.20           82.5 / 84.2 / 84.2
     gamma_sim = 0                  60.0  (calibration is
                                          load-bearing in sim)
     gamma_sim x 0.5                65.8
     denoised-D s=0.10 / 0.15       83.3 / 83.3
     dir-coeff 0.15 / 0.25          78.3 / 80.8
     dir-coeff 0.30 (bias s=0.10)   85.8  (80.0/85.0/92.5)
     dir-coeff 0.30 + denoised-D    85.0
     dir-coeff 0.30, bias s=0.15    84.2
   (An earlier run of this instrument had a fold bug —
   per-fold reshuffles made test sets overlap and left
   40 items unpredicted; caught because fold-wise
   centroid scores (0.67-0.83) contradicted the printed
   aggregate (0.533), fixed to a single stratified
   partition, all numbers above are from the fixed run.)

## Design (frozen by this statement)

One lever, chosen by the cross-fitted instrument and by
the mechanism story, not by full-diagnostic score:

  AMPLIFY THE DIRECTION TERM relative to everything
  fitted: direction coefficient 0.20 -> 0.30 on the same
  diagnostic class-mean directions D_c, with the bias
  term kept at round 1s scale (s_bias = 0.10) and
  calibration re-derived by round 1s exact procedure
  (gamma_full measured on the real model at this
  config; gamma_sim from fixed-H coordinate ascent at
  this config; at most two fixed-point residual steps
  against the sim target, round 1s stopping rule).
  No subtype-specific edits. No new fitted constants
  beyond the re-derived gamma. Dose unchanged in count:
  3 rows x 1024 x 2 tied copies = 6,144 scalars
  (0.00082%, limit 0.1%).

Rationale: raising the direction coefficient raises the
per-item, class-conditional signal relative to (a) the
base rows alarmed prior and (b) the per-class constants
(bias + gamma), which are the world-specific parts.
Cross-fitting — the only transfer proxy available
without touching held-out — ranks this first of the
eleven predeclared variants and gives it the most
balanced per-class profile. Denoising was tested and
dropped: at dir-coeff 0.30 it costs 0.8 CV points.

Fallback (predeclared): if the real-model build of this
config scores < 70% on the official diagnostic scorer
or any class < 50%, fall back to denoised-D s=0.15
(CV 83.3) built by the same procedure; if that also
fails the floor, declare round 2 a no-build and round 1
stands.

## Predicted held-out effect (recorded before building)

Held-out 55-65% overall (round 1: 50.8), calm recall
40-55% (round 1: 27.5 — the class this design aims at:
a stronger calm direction is the only component that
can out-argue the alarmed prior on unseen calm rooms),
alarmed 65-80%, stampede 55-70%. Risk, stated: direction
amplification also amplifies any rotation of the hidden
geometry in the unseen world, and the real-model input
coupling grows with delta norm; if the re-derived
calibration cannot hold the fixed point as cleanly as
round 1s (residual <= ~1.3 logits), diagnostic will
show it first and the fallback rule fires.

## Amendment A (2026-11-04, recorded after the builds above,
## before any official-scorer run on the amended design)

The dir-coeff 0.30 design FAILED on the real model, and the
predeclared fallback chain was run and also failed:

  config (all by round 1s calibration procedure)   real argmax
  dir 0.30, bias 0.10, gamma re-derived, fixed-    65.0
    point iterated to convergence (residual
    <= 1.3; DESIGNs two-step cap assumed round-1-
    like convergence — measured contraction here
    was geometric ~0.28x/step from a 14x larger
    initial residual, so iteration continued to
    the round-1 stopping rule; deviation recorded)
  denoised-D s=0.15 (predeclared fallback)         69.2
  dir 0.25, bias 0.10 (predeclared CV grid)        66.7
  dir 0.15, bias 0.075 (dose reduction)            77.5 argmax
    BUT official scorer 56.7 (stampede 27.5):
    generation diverges from 3-row argmax — at
    this dose the spaced label rows no longer
    dominate the bare alarmed token in free
    generation. Rejected by the floor rule.

Measured mechanism for the amplification failure:
per-item coupling offset std grows with delta norm
(dir 0.30: delta norms 1.77-2.02, offset std
7.4-10.6 logits; round 1: norms 1.18-1.35, std
4.9-7.2). Fixed-H simulation cannot see this; it
ranked dir 0.30 first. The real-model dose curve
(argmax): dir 0.10: 70.8, 0.15: 77.5, 0.20: 81.7
(round 1), 0.25: 66.7, 0.30: 65.0 — round 1 sits at
the real optimum, and its remaining held-out gap is
therefore NOT a dose problem.

Amended design (the remaining robustness lever, named
in the round-2 brief itself: regularising calibration
toward the raw class-mean geometry): keep round 1s
dose and geometry EXACTLY (dir 0.20, bias s=0.10,
same directions.npz); change only gamma by shrinking
its most diagnostic-fitted component — the fixed-point
residual correction gamma_resid = [+0.0039, +0.0412,
+0.0068], worth +5.0 diagnostic argmax points in
round 1s own record — by the standard shrinkage
factor 0.5 toward the un-fitted calibration:
  gamma = gamma_full + gamma_sim + 0.5 * gamma_resid
        = [+0.00066, +0.17204, +0.05343].
The alarmed residual alone is a +7.6-logit constant
boost to the alarmed row fitted on diagnostic means;
halving it is the direct counter to the held-out
confusion pattern (calm->alarmed 27/40,
stampede->alarmed 17/40). Shrinkage factor 0.5 is
stated here BEFORE the amended patch is built or
scored. Floor rule: official diagnostic scorer
>= 70% and no class < 55%, else no-build (round 1
stands). Round 1s record gives this gamma family
argmax 76.7 (its phase-D t=0.5 step).

Predicted held-out for the amended design (recorded
before building): 53-62% overall vs round 1s 50.8;
calm 35-50 (from 27.5), alarmed 68-78, stampede
50-62. The bet is narrow and stated: half of round 1s
residual-fitted alarmed boost was diagnostic weather,
not climate.
