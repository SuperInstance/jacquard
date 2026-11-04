# Slice 43 (part 4) — E8: a custom decision model

Casey's target: the advisor behind Jacquard's provider
seam, specialised on how THIS operator weights decisions.
The curriculum is the fleet's own record. Constitutional
line, stated here as in every E8 artefact: the custom
model remains a SENSE behind the seam — sharper, more
personal readings; the kernel and the record still gate.

Battery (`experiments/wsp/e8/`): 166 recorded decisions
curated from the shadow trial, the proof runs, the jev
experiment, gpu-queue windows, and the schedule board —
rendered as compact contexts (producer, effect, resource,
timing/policy facts) with the recorded outcome as gold.
Split BY TIME at 2026-11-03T00:00Z: diagnostic 112
(72 ALLOW / 37 HOLD / 3 DENY), held-out 53 (47/1/5 —
one item dropped by the coordinator before any scoring:
`e8-gpu-windows-005`, whose job name, jacquard-held-1,
announces its own outcome). The curation method was
validated against the published shadow trial: replaying
the trial's scanned history reproduces it exactly
(52 decided, 46 agree, 3 incumbent-wrong, 3 policy-gap).
Four incumbent-wrong items are marked with the correct
outcome and its evidence (3 in diagnostic, all recorded
ALLOW where contention required HOLD; 1 in held-out,
recorded DENY of a sentinel the tightened policy allows).

Dual scoring, always separate: (a) agreement-with-the-
operator, (b) agreement-with-correctness where known
(diagnostic subset n=105; held-out subset n=14 — wide
noise, ±23 points; the held-out (a) split is ALLOW-heavy
by the record's nature, so diagnostic carries the fine
structure and held-out is a coarse check).

Student base rates (fresh Qwen3-0.6B, coordinator-
measured): a CONSTANT-ALLOW machine — 112/112 diagnostic
and 53/53 held-out answers are ALLOW, so its scores are
exactly the majority-class rates: (a) 64.3% diagnostic /
88.7% held-out, (b) 59.0% / 64.3%. It has no decision
surface at all. The loop's question is whether authored
patches can carve the operator's actual boundary —
contention and exclusivity facts flipping ALLOW to
HOLD — into it, and whether what gets carved is the
policy (both scores rise) or the sycophancy (only (a)).
Programme baselines for scale: stock advisor 10/11 on
its experiment (miss = HOLD flattened into DENY);
shadow trial 88%.

Round 1 — the patch (HOLD/DENY label rows only, direction
edits from diagnostic class means; 4,088 scalars) learned
what is linearly present in the record: on diagnostic,
(a) 64.3 -> 96.4 and (b) 59.0 -> 93.3 (board and proof
records reproduced perfectly; all 4 residual errors in
the jev cluster). The geometry probes found the ALLOW/
HOLD boundary strongly present (projection AUC 0.971) —
but mostly as source/class structure (protected effects
without a standing rule -> HOLD), not as a general
contention policy.

The crux, answered at item level: the three diagnostic
incumbent-wrong cases (recorded ALLOW, correct HOLD —
same-seat contention the operator waved through) are all
answered ALLOW by the patched model. The operator's
error is learned, not the policy — and the probes show
why: overlap text is encoded, but the same-exclusive-
seat relation is not linearly separable at usable margin
(the trio's projections are indistinguishable from legal
overlaps on other seats). A linear row patch cannot
learn what the representation does not separate.

Held-out verdict (coordinator): ITEM-IDENTICAL to the
unpatched student — 53/53 ALLOW, (a) 88.7, (b) 64.3.
Zero transfer: the learned structure is bound to the
diagnostic era's formats, and the later record (gpu
windows, slice-30 bookings) arrives in formats the
curriculum never showed. The adoption proposal was
DENIED from this record (governance proposal fc24c303).

E8's findings, plainly: (1) the dual score works — it
caught, at item level, the difference between learning
the operator and learning the policy; (2) what a patch
can install is bounded by what the base representation
already separates — the weighting that matters most
here (contention on the same exclusive seat) is exactly
the part it does not; (3) a custom advisor fitted to one
era's formats reads the next era as its majority class.
The custom decision model is not refuted as an idea;
its preconditions are now measured: a representation
that separates the operative relation, and a curriculum
whose formats cover the deployment's. Neither held here.
