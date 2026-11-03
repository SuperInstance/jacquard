# Slice 25 — gpu-queue live, window 2 (2026-11-03)

Second bounded live window on the Thor's real gpu-queue,
continuing the slice-22 log under slice 22's constraints
verbatim. Evidence: `docs/slice25/kernel.jsonl` (the live
log at close, 197 entries, sha256
edad69c8657db20e0c2e1891ac1d37ea2049c41282c7a8871651804e16d588b0),
its bridge journal, and the shadow analysis
(`docs/slice25/shadow_analysis.py` + `shadow-rows.json`).

## Bounds and bookings

Oracle lane booked (agent-inbox e1a3975), Thor cpu booked
(agent-inbox 8e47c90). Zero new persistent processes or
services on the Thor; feeder OFF throughout (verified at
open, mid-window, and close); the bridge crossed only
per-dispatch over the existing SSH door; the incumbent gpuq
was the only dispatch path; jobs only in the governed lane
`jacquard`, class `gpu-bench`. Bounds were stated in the
builder's log and in the log itself (the window-2
`gpu-policy-record`, seq 91) before the first dispatch, and
the window is anchored at both ends: checkpoint seq 2
`gpu-live-window-2-open` at length 92 (anchors 3b31b71) and
seq 3 `gpu-live-window-2-close` at length 197 (anchors
7005e99). At close the grown log verifies **197/197 via the
registry path in all three implementations** (Python, TS,
Rust — slice 24's fix carrying a live window end to end).

## Counts

Whole log at close (bridge `counts`, chain_ok true):
submitted 17 · allowed 10 · held-at-submission 2 · denied 5 ·
dispatched 12 · completed 10 · failed 1 · entries 197.

Window 2 alone: **submitted 9 · allowed 7 · held 1 ·
denied 2 · dispatched 7 · completed in-window 6 · failed 1**.
(One further completion, job-7 — window 1's sentinel — was
dispatched in window 1 and ran in window 2, as designed.)
The 9th submission is a recorded deviation: the plan stated
8; a third sentinel (below) made 9.

## What happened, including the two deviations

Beat 1 decided exactly as designed: bench-4, bench-5
allowed; net-1 (mystery-lane, network fetch, no execution)
held and released by one hash-bound operator decision
(binding 5e8e079a…); feeder-on-2 and fetch-exec-2 denied by
shape. Beat 2: bench-6 (consumes bench-2), bench-7
(consumes the sentinel artifact), sentinel-2 — all allowed.

**Deviation 1 — bench-7 failed and halted the queue.**
bench-7's command reads `prev['sum']` from `sentinel.json`,
but the sentinel artifact is a note, not a bench result —
it has no `sum` (job log: `KeyError: 'sum'`). A window-design
error in the consuming job, authored by the coordinator.
gpuq retried once, then halted dispatching entirely, per its
documented start-failure policy — the incumbent's fail-stop
working as characterised since Phase 1. The halt is cleared
by the operator in `queue.json` (no CLI verb exists; the
daemon never clears it in code): the coordinator cleared
`meta.halted` under `queue.lock`, changing nothing else,
and recorded the intervention in the log itself
(`gpu-operator-note`, seq 188). The failed job stayed
failed and was not retried. After the clear, sentinel-2 and
bench-6 ran; bench-6's artifact embeds bench-2's exact sum
(-32816.18359375).

**Deviation 2 — a third sentinel.** gpuq's dispatch order
left bench-6 last in its queue, where the successor rule
would have stranded it; sentinel-3 was submitted behind it
so bench-6 could run and sentinel-3 — not the consuming
job — stands queued at close. Consequence stated plainly:
sentinel-2, planned as the standing sentinel, RAN (its
artifact exists, unused); the standing queued job at close
is sentinel-3 (job-14), the only queued job on the Thor.
Feeder OFF; gpuq lifetime at close: 1,647 done, 1 failed
(the 1 is bench-7).

## Operator accounting (one formula, both windows)

Operator minutes = decision events × per-decision handling.
The net-1 release measured ~1 minute of operator attention
(queue presentation read, binding checked, bound approval;
machine time ~1.4 s end to end). Window 1: 1 event /
8 submissions = **12.5 events per 100 actions ≈ 12.5
min/100** (the 1-minute handling applied retroactively as a
labelled estimate — window 1 recorded no timing). Window 2:
1 event / 9 submissions ≈ **11 min/100**. Flat, and said
plainly: the queue did not shrink, because no learned rule
was earned — mining over window 1 found 0 candidates, and
mining over the doubled corpus at close still finds **0**.
The structural reason is named: for this job class every
command text is unique (job names are embedded), so shape
signatures over the full text essentially never repeat and
support never reaches the bar. Signature granularity was
already a recorded spec choice (Phase 6 residuals); this
window is its live consequence. The halt-clear was a second
operator action, but not a decision-queue event; it is
counted here in prose, not in the formula.

## Headline — downstream use

The `gpu-downstream-use` sense over the whole log at close:
**10 completed outputs, 3 used, ratio 3000 bp** (window 1:
1 of 4, 2500 bp). Used: bench-1 (window 1, by bench-3),
bench-2 (window 2, by bench-6), sentinel (window 2, by
bench-7 — a declared use and a real read; the consuming job
then failed on the artifact's shape, so the use was an
attempted consumption, not a successful reuse — counted by
the sense's method, qualified here). Seven outputs were
never consumed by anything. The churn disease remains the
live log's headline: governance did not manufacture demand,
and in two windows the fleet's governed GPU work produced
three consumed artifacts out of ten.

## Shadow consumption policy (analysis only)

Scored strictly causally over both windows' streams (a
submission is priced only by what the log recorded before
it; `docs/slice25/shadow_analysis.py`). Window 1: the policy
could not fire — no producer had a track record at any
submission (the cold-start exemption). Window 2: **3
would-holds — bench-4, bench-5, bench-6 — all true
positives** (their outputs were completed and never used);
0 false positives; under the refinement (exempt
self-consuming submissions) 2 would-holds, both true
positives (bench-6 exempted as a consumer). bench-7 was NOT
a would-hold: bench-6's declared use, recorded at its
submission, had already lifted jacquard-build's trailing
ratio to 6667 bp — the policy would not have prevented the
failure. Costs: the 3 holds would have added 3 decision
events (~44 events/100 for the window) to save ~60
GPU-seconds of ~20-second benches. Verdict: the policy
fires accurately but prices the wrong resource at bench
scale — operator minutes are dearer than bench GPU-seconds;
consumption-pricing belongs on job classes whose GPU time
dwarfs a minute of attention. Two policy gaps named:
(1) cold-start — with no track record the policy is blind,
exactly when a new lane is most prolific; (2) the trailing
ratio counts DECLARED uses (recorded at a consumer's
submission) before the consuming job has run — a promise
flatters the ratio (bench-7 was priced on bench-6's
promise; had bench-6 failed, the flattery would stand).
Live behaviour was not changed by any of this.

## Disagreements and regretted rules

Regretted rules: none — no learned rules exist on this log
to regret, and the bridge policy's two window-2 denies were
both correct. Jacquard wrong: 0 (bench-7's failure was a
job-content error by the submitting coordinator, not a
policy miss; the bridge correctly allowed a well-formed
job of the governed class). Incumbent wrong: 0 (the halt
was its documented policy doing its job). Policy gaps: the
two shadow-analysis gaps above, plus the signature-
granularity observation in the accounting section.
