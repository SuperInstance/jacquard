# Slice 43 (part 3) — E7: a soft joint for the signal chain

Casey's application target: signal-chain's workflow spine
is hard (decision-tree structure); its soft joint is the
equal-weight balance mapping in `signal_chain_dial.py::
_score` that reads a message as code / mixed / model.
E7 tests whether a small specialist, coached by authored
patches in governed rounds, can be that joint — spine
untouched and auditable, the joint's coaching itself a
record (this file + the governance log pattern of E6).

Battery (`experiments/wsp/e7/`): 120 diagnostic + 120
held-out messages, 40/40/40 code/mixed/model, labels by
construction, disjoint template pools per split (an early
draft's held-out was a reskin — the Jaccard check caught
it at 0.92 and the generator was rewritten; cross-split
max now 0.324). 49 boundary-flagged items per split
plant code-dense prose, error-shaped prose, polysemy,
prose-named identifiers, and friends.

Baselines (coordinator-measured):
- The incumbent joint (dial, equal-thirds thresholds,
  untuned): diagnostic 61.7%, held-out 46.7% — and mixed
  nearly invisible to it (held-out mixed 3/40).
- The student (fresh Qwen3-0.6B, fixed classification
  prompt, zero-shot): diagnostic 36.7% (code 25%, mixed
  0/40 — it never says mixed, model 85%), held-out 41.7%.
  Two attractors and no mixed basin: a decision-surface
  failure, the shape authored patching exists for.

Rounds follow. The standard is the construction labels
(the teacher's readings); the incumbent to beat is the
dial; per-class numbers are reported throughout because
an aggregate can hide a dead class.

Round 2 — a logistic-probe refinement: diagnostic rose
81.7 -> 88.3 (model class fully repaired, 85 -> 100;
the whole code-dense design-note block fixed). The
coordinator's held-out verdict REVERSED it: 80.0%, below
round 1's 84.2% — code and model improved again, but
mixed fell 75 -> 55, traded away on held-out while the
seen battery rose. Textbook divergence (seen improves,
held-out falls), with ~35 generation configs searched
on 120 diagnostic items as the parsimonious mechanism:
the refinement tuned the instrument, not the joint.
Adoption DENIED from the record (governance proposal
7f652e1f); round 1 stands as the joint.

E7 close: the specialist that ships in this record is
round 1 — held-out 84.2% against the incumbent joint's
46.7%, mixed 75% against 7.5%, 6,144 authored scalars,
ablation-exact, its coaching rounds (one adopted, one
rejected) both in the governance log. The spine was
never touched. The loop also produced its own guardrail
evidence: round 2 is what an unguarded loop would have
shipped.
