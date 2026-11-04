# Phase 17 W1 — re-coaching round 2: coordinator verdict

Scored by the coordinator (the patcher never saw either
held-out). Patcher prediction, recorded before scoring:
live graded 55-70% (point ~62); battery held-out 72-82%,
mixed 65-85%.

## Measured

Live graded sample (66, blind grader gold):
- Round 2: 34.85% (round 1: 27.3%). Per class: code 19/20,
  mixed 0/20, model 4/26. Predicted mix: code 55, model 11,
  mixed 0 — mixed is never predicted on live items.
- The in-sample live-diagnostic repair (88.0%, model 8/9)
  did not transfer to unseen live items: model 4/26.

Battery held-out (120, retention check):
- Round 2: 71.67% (round 1: 84.2%). Per class: code 75%,
  mixed 55%, model 85%. A -12.5 pt retention tax, mixed
  dented (75 -> 55) but not collapsed.

Prediction scoring: battery essentially right (71.67 vs
72-82 band edge); live badly over-optimistic (34.85 vs
55-70) — the patchers own named risk (mixed on long
documents) was the failure, larger than its caveat.

## Decision: round 2 DENIED as the shadow specialist

It buys +7.6 live points at -12.5 battery points and still
leaves the wild class structure unrepresented (mixed dead,
model 15%). Neither round meets the pre-stated
survives-contact bar (>=74.2%). The lesson the round prices:
the failure is not dose or weighting — four weighting
schemes were measured and rejected during construction —
it is that the joint, as coached on short messages, does
not exist in this traffic. Live items are long documents
whose class boundary (code vs mixed vs model on a
30,000-char cumulative log) is contested between two
independent blind readers themselves (grader: mixed 20/66;
teacher: mixed 1/25 on a disjoint set, prospector logs
read as model by one, mixed by the other). A readout
cannot be coached onto a boundary its teachers draw in
two places. Round 1 remains the recorded specialist;
both rounds stand in the record with their evidence.
