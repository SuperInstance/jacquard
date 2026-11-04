# Phase 17, W2 — inventory of candidate joints, and the pick

Worker: W2 inventory+battery builder. Date: 2026-11-04.
Pick rule: CRITERIA.md §W2, applied as written — a joint must
have (a) >= 500 historical real events with labels derivable
from recorded outcomes, no new human labelling of the training
split; (b) an incumbent behaviour recorded in the same record;
(c) a hard spine it sits inside. All counts below were measured
live on 2026-11-04 from the records named; counting scripts are
in `w2/` beside this file's battery artefacts
(`count_gpu.py` run on the Thor; the Oracle counts run against
`~/jacquard-p11-bookings/kernel.jsonl`, `~/agent-inbox` git).

Environment note (deviation, stated): the Oracle root disk is
100% full (45G/45G, 0 avail) at W2 start, so the instructed
clone at Oracle `~/jacquard-p17-w2` could not be created
there. This work was done in an identical clone of
`phase17-practice` (tip 5a38316, via a git bundle taken from
the coordinator's Oracle clone `~/jacquard-p17`, bundle
sha256 9081beff…) on the worker VM, branch `p17-w2`, pushed
to the same GitHub remote. Thor work is in `~/wsp-exp17/w2/`
(copies only; nothing resident mutated; no downloads).

## Candidate 1 — gpu-queue job-shape classification (Thor)

Record: `~/gpu-queue/events.jsonl` (3,320 lines, verified),
`queue.json`, `status.json`, 1,651 job-logs, `idle.jsonl`
(1,600 lines). Range 2026-10-27T23:22-0800 → 2026-11-03T20:50-0900.

- events by type: dispatch 1,651 · finish 1,649 ·
  no_successor_hold 10 · daemon_error 8 ·
  start_failure_retry 1 · start_failure_halt 1.
- jobs in `queue.json`: 1,651 — kind: feeder 1,635, finite 16;
  lane: foundry-loop 1,637, jacquard 14; status: done 1,649,
  failed 1, queued 1; exit: 0 ×1,649, 1 ×1, none ×1.
  Every `finish` event in events.jsonl has exit 0 (1,649/1,649).
- The only balanced recorded class over >= 500 events is the
  foundry archetype: fishing_boat 410, harbor_house 410,
  pier 409, spruce 408 (n=1,637 incl. 2 finite foundry jobs).
- BUT the archetype label is verbatim in the job's own text
  (`--archetype <label>` in `cmd`, and in `name`). The whole
  corpus has only 13 digit-normalised command templates and
  12 name templates. Under the CRITERIA temporal split
  (earliest 70% / latest 30% of the 1,651 jobs): diagnostic
  1,155 jobs (feeder 1,153, finite 2), held-out 496 (feeder
  482, finite 14) — and 482 of the 496 held-out jobs (97.2%)
  have a digit-normalised template that already appears in
  diagnostic. This is the reskin failure E7's Jaccard check
  caught in Phase 15, at fleet scale.
- The non-trivial judgement labels in this record are dead
  or tiny: outcome (exit) has 1 failure in 1,650 completed
  jobs; successor-hold has 10 events; the Jacquard bridge's
  genuinely judgement-shaped record (slices 22+25: submissions
  classified allow / deny-by-shape / hold, incl. the Phase 8
  feeder-shaped denial) totals **17 submissions** (shadow-rows:
  allow 10, deny 5, queued/held 2; fates: completed 10,
  never-dispatched 6, failed 1) — see
  `docs/slice25/shadow-rows.json`, `docs/slice25-live-report.md`.
- (b) incumbent: recorded — the daemon's own handling
  (dispatch/finish/hold per job, `daemon.py`: successor rule,
  feeder materialisation by rotation, start-failure halt).
  For the archetype class the incumbent is a deterministic
  parse/rotation rule and scores 100% by construction (gold
  and prediction are the same recorded field).
- (c) spine: yes, hard — `gpuq` daemon (successor rule,
  fail-stop halt), `mint.py`, and the Jacquard bridge policy
  over it. Nothing about the spine is soft.

Verdict: (a) passes on raw count, fails on substance — the
>= 500-event label is a lookup copied in the input, not a
judgement, and every judgement-shaped label in the record is
below 500 by two orders of magnitude. (b) yes. (c) yes.

## Candidate 2 — booking-board contention support

Records: live log `~/jacquard-p11-bookings/kernel.jsonl` =
**260 entries** (the brief's figure — but they are governance
log entries: machine 8, definition 7, transition 157,
decision 29, execution 23, sense 36; the repo copy at
`docs/slice30/booking-log.jsonl` is an older 197-entry
snapshot), plus board history in `~/agent-inbox/schedule/`
(121 schedule-touching commits; ≈149 board rows ever added).

- Distinct governed booking units in the live log: 13
  (7 imported at init + 6 applied through the gate:
  oracle-box, orin-zcode ×3, proart-zcode, thor-detached).
- Distinct contention evaluations: 6 sense names.
- Real contention events (a booking actually held against
  another): **1** — the Orin zcode tie of 2026-11-03
  (proposal 62ad96e5…, held, later operator-released;
  `docs/slice30-device-matrix.md`: "the only queued item in
  the log"). Phase 16's note that governed-end labels are
  thin here is verified, and understated: the positive class
  has one member.
- (a) FAIL by ~487 events even counting every log entry as
  an event (260 < 500), and by ~499 on the label that
  matters (contention: 1). (b) yes (jqbook contention sense
  + tie disposition recorded). (c) yes (booking machine /
  jqbook spine).

## Candidate 3 — agent-inbox task routing

Record: `~/agent-inbox` git history, 280 commits total,
2026-10-06 → 2026-11-04.

- Distinct tasks ever in inbox/claimed/done flow: **25**
  (slugs 000–024). Claim commits: **22** (laptop 19 incl. one
  annotated, prospector 3). Done commits: 32. Current tree:
  inbox 1, claimed 0, done 24.
- Incumbent (who claimed what) is recorded in the claim
  commits — (b) yes in form — but with effectively one
  claimant (laptop 19/22), the routing label is near-constant
  as well as tiny.
- (a) FAIL by ~475 (25 tasks / 22 claims against a 500 bar).
  (c) partial: the inbox→claimed→done protocol is a real
  workflow, but there is no hard spine enforcing routing —
  claiming is by convention (PROTOCOL.md), nothing gates it.

## The pick

**No candidate satisfies all three criteria in substance.**
Per CRITERIA.md §W2 that outcome is a deliverable, not a
failure: the nearest miss is named and the gap stated.

**Nearest miss: candidate 1, gpu-queue job-shape.** It is
the only candidate with (b) and (c) fully real and (a) met
numerically (1,651 jobs / 3,320 events). Its exact gaps,
measured (the battery in W2-BATTERY.md exists to make these
numbers reproducible, not asserted):

1. Label-is-in-the-input gap: the only >= 500 balanced class
   (foundry archetype, n=1,637) is copied verbatim into every
   item's text; the incumbent deterministic rule scores
   100% on both temporal splits, so the CRITERIA shadow bar
   (held-out >= incumbent + 10) is unreachable by
   construction — there is no headroom for a specialist.
2. Dead-outcome gap: recorded job outcome is 1,649 successes
   / 1 failure / 1 queued — no failure class exists to learn.
3. Judgement-record gap: the record that does contain the
   real judgement (bridge allow/deny/hold over submissions)
   has 17 events; reaching (a) needs >= 483 more governed
   submissions of that kind. The finite lane-submitted job
   record has the same shape of gap: 16 finite jobs against
   the 500 bar (>= 484 short), 14 of them in the held-out era
   alone, leaving a 2-item finite diagnostic.

What would close the gap: continued governed gpu-bridge
traffic (slices 22/25 pattern) until submissions with
recorded allow/deny/hold outcomes reach 500, or an equivalent
volume of finite lane submissions with recorded outcomes.
Until then a W2 patch round would be coaching a lookup —
exactly the parlor shape Phases 15/16 taught this programme
to refuse. The battery, incumbent scorer and zero-shot
student baseline for the nearest miss are nevertheless built
and measured (W2-BATTERY.md), so the refusal is priced and
reproducible, and the harness is ready unchanged for the day
the judgement record reaches the bar.
