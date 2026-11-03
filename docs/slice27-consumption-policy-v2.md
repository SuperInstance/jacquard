# Slice 27 — consumption policy v2: findings and re-scored shadows

Phase 10, slice 27. The v1 shadow analysis (Phase 9, slice
25) ended with two named gaps in its own semantics. This
slice fixes exactly those two, re-scores the same frozen
evidence (the two live windows' log,
`docs/slice25/kernel.jsonl`, 197 entries), and reports the
deltas. The v2 semantics live in ONE implementation —
`adapters/consumption.py` — which the shadow scorer
(`docs/slice27/shadow_analysis_v2.py`) and the bridge's
consumption gate (slice 28) both call, so a shadow score
and any future live behaviour cannot drift apart.

## The two fixes

**1. Promise flattery — the ratio counts completed
consumption only.** v1 counted a use when a consuming job
*declared* it (its execution entry is written at
submission/dispatch). A declaration is a promise: it lifted
the producer's trailing ratio before the consuming job had
run, and the lift stood even when that job then failed. v2
counts a use only when the consuming job's *completion* is
recorded in the log (`gpu-outcome`, status completed)
before the priced submission. The consumer ran, read the
output, and finished — or the use does not exist for
pricing purposes.

**2. Cold start — an exemption budget, claimed in the
accounting.** v1 exempted a producer with no recorded
completions: invisible, unbounded, and blind exactly when a
new producer is most prolific. v2 replaces it with a budget
denominated in *completed outputs* (default 3, policy
data): while a producer's completed-output count is below
the budget, its submissions are exempt from a consumption
hold — and every exemption actually spent (an allowed,
output-declaring submission priced inside the budget) is
recorded as a CLAIM, in the shadow rows below and, when the
gate is live, in the per-item `gpu-policy` sense entry. The
fleet can therefore see what the grace cost: in windows
1+2 the budget bought exactly **4 claims**, all in window 1.

Why this shape, against the candidates:

- *Pricing at the fleet trailing median* imports other
  producers' behaviour into a new producer's price: an
  honest newcomer in a churny fleet is priced as a churner,
  and the median is gameable by anyone who can add a
  producer. Rejected.
- *Probation with a stated sample floor* is mechanically
  near-identical to the budget — but its exemptions are
  silent. Jacquard's whole thesis is that the record is
  the product; an exemption that leaves no trace is a
  decision nobody can audit. The budget's one addition —
  the claim, recorded per exemption spent — is the entire
  difference, and it is why this candidate wins.
- Denominating the budget in completed outputs (rather
  than capping claim count) is deliberate: it drains only
  as evidence lands. A producer whose jobs are still in
  flight — the normal case for the expensive class this
  policy targets, where one job runs minutes — keeps its
  exemption, because there is genuinely nothing to price
  on yet. The cost of that choice is stated plainly: in a
  burst, claims can exceed the budget number (4 claims
  against a budget of 3 below), because several submissions
  can be priced before the first completion lands. The
  exposure is bounded by the producer's in-flight window,
  not by the budget; a claim-count cap is the stricter
  variant and remains available as policy data. The shadow
  accounts claims either way, so the operator sees the
  number before choosing.

The threshold (5000 bp = 50%) and v1's condition (a) — the
priced output must have no declared consumer in an earlier
execution entry — are unchanged. Condition (a) is itself
promise-based *by design*: a named future consumer is a
commitment, and the commitment is later graded by this
same ratio when the consumer completes (or doesn't). It is
recorded here as a known residual, not silently redesigned.

## Re-scored shadows: v1 → v2 (strictly causal, same log)

Window 1 is unchanged in outcome: every submission was
priced inside the exemption budget (no completions existed
at any window-1 pricing), 4 claims recorded. The policy
could not have held anything in window 1 under either
version — now with the grace accounted instead of assumed.

Window 2 deltas (v1 → v2):

| submission | v1 ratio / verdict | v2 ratio / verdict | fate |
|---|---|---|---|
| bench-4 | 3333 / hold | 3333 / hold | completed, unused — true positive |
| bench-5 | 3333 / hold | 3333 / hold | completed, unused — true positive |
| bench-6 | 3333 / hold (refined: exempt) | 3333 / hold (refined: exempt) | completed, unused — true positive |
| bench-7 | 6667 / **no change** | 3333 / **hold** (refined: exempt) | **failed — true positive (wasted work)** |
| sentinel-2 | 6667 / **no change** | 3333 / **hold** | completed, unused — true positive |
| sentinel-3 | 5000 / no change | 1667 / **hold** | never dispatched — no GPU time at stake |

Totals: would-holds 3 → **6** (refined 2 → **4**);
true positives 3 → **5**; false positives **0 → 0**;
no-stake 0 → 1.

**The bench-7 repricing** is the headline the brief asked
for. Under v1, bench-6's declared use of bench-2's output —
recorded at bench-6's submission, before bench-6 had run —
lifted jacquard-build's trailing ratio to 6667 bp and
bench-7 sailed through at no-change; bench-7 then failed
on a malformed read and halted the queue. Under v2 that
promise counts for nothing until bench-6 completes, so at
bench-7's pricing the ratio stands at 3333 bp and the raw
policy **would have held bench-7** — a true positive in
the wasted-work sense: the hold would have saved the
wasted GPU time (two failed starts), not prevented the
bug, which was a job-content error no consumption policy
claims to catch. The *refined* policy still exempts
bench-7 in both versions, because bench-7 itself declares
a consumed input and the refinement protects consumers —
the refinement's price is visible in this row and is
recorded as such.

**sentinel-3 is v2's honest blemish.** Its would-hold is
new (v1 priced it at exactly the 5000 bp threshold) and
carries no GPU time at stake — sentinel-3 never dispatched;
it stands queued *by design* as the window's declared
successor, the mechanism that let bench-6 run at all. The
policy cannot distinguish a declared successor — a job
whose purpose is to be queued, whose "output" is a note —
from churn. Named residual for any live activation: a
policy-visible successor/sentinel marker on the submission
(the bridge knows the role today; the policy record does
not), so the gate can exempt the role by declaration
rather than by outcome. Until that marker exists, a live
gate on a class that uses successor sentinels will spend
operator decisions on them.

## What v2 does not change

The bench-scale verdict from Phase 9 stands untouched: on
~20-second benches these holds — however accurate — still
spend operator decisions to save GPU-seconds. v2 makes the
policy *honest* (no promise flattery, accounted grace);
slice 28 takes it to the classes where the exchange rate
could actually pay, or reports that there are none.
