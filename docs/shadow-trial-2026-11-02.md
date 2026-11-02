# Shadow trial report — Jacquard beside the booking board

**Date:** 2026-11-02. **Tool:** `tools/shadow_trial.py`.
**Stream:** the agent-inbox booking board (`schedule/*.md` in
`~/agent-inbox`), full git history 2026-10-27 → 2026-11-02,
63 commits touching `schedule/`. Window and counting rules were
stated in the builder's log before the trial ran.

## Method

Every booking row's first appearance in the history is one
proposal item (68 items). The incumbent outcome for every item
is *accepted* — the board took them all. The shadow expressed
each as a Jacquard proposal (producer = lane, class "booking",
a write of the booking unit) to a real shadow Sequencer, and
combined policy/1's outcome with a contention flag: overlap
with an active booking on an exclusive seat of the same box
(same-lane overlaps are renewals; bookings past their check-by
are dead by the board's own protocol and do not contend;
`detached` contends only with `box`).

The contention flag is computed by the harness, not by a
dictionary word — deliberately, and this is a finding: interval
overlap over a list of booking maps is **not expressible with
the current 26 primitives** (there is no iteration over lists).
Any production contention rule needs either a new primitive or
a sense that pre-computes contention — the design record's
extension rule (R16) says that decision belongs to a spec
revision, not to an implementer's improvisation.

## Numbers

| | |
|---|---|
| Proposal items | 68 |
| Retroactive notes (decided allow, excluded below) | 6 |
| Unevaluable (start/duration unparseable) | 10 |
| Decided items | 52 |
| Shadow agrees with incumbent (allow) | 46 |
| Disagreements (shadow would queue) | 6 |
| **Agreement rate (decided items)** | **46/52 = 88%** |

## The disagreements, classified

Classes: **Jacquard wrong** = the shadow rule misfired on the
data as it was. **Incumbent wrong** = the booking violated the
board's own protocol. **Policy gap** = a situation neither
policy/1 nor the board protocol can express, where a human
waved the item through and the missing piece is a concept
(conditional start, priority override), not an error.

1. **Policy gap** — thor, `system-three-paper` (kimi, 20:35)
   vs `cold-librarian` (box, 19:37). A REBOOK whose text says
   "starts when the paper lands; no GPU": a conditional,
   resource-light booking. Queueing it asks a human to approve
   what the text already explains; the board has no field for
   either property.
2. **Incumbent wrong** — proart, `otherhere-rebuild` (box,
   21:30) vs `system-three-paper` (claude-code, 20:35, live to
   22:35). A whole-box claim over a live exclusive seat, no
   declared exception in the row.
3. **Policy gap** — thor, `otherhere-rebuild` (box, 21:30) vs
   the same conditional kimi REBOOK as (1): the overlap is with
   a booking whose real occupancy is event-driven and unknown.
4. **Incumbent wrong** — thor, `eden-trial` (box, 23:00) vs
   `system-three-wrapup` (box, 02:00). The 23:00 whole-box
   booking ran into the live 02:00 whole-box booking; the fleet
   then had to re-plan wrapup to 00:50 ("supersedes the 02:00
   row") — the conflict was real and cost a shuffle.
5. **Policy gap** — thor, `casting-call-revisability` (gpu,
   23:57) inside `eden-trial`'s box window. The row is a
   Casey-directed successor probe: an authority priority
   override. A queue would have been released immediately;
   neither the board nor policy/1 can carry the captain's
   priority inside the proposal.
6. **Incumbent wrong** — thor, `whole-house-stage0` (box,
   02:00) at the same moment as wrapup's box booking. Stage 0
   was light read-only measurement (its sibling row admits
   "No seats driven, nothing changed"): it over-booked the
   exclusive `box` seat for work that needed no seat. No harm
   resulted; the double-claim on an exclusive seat is still
   the board's error, not the shadow's.

**Jacquard wrong: 0 in the final run — but 14 in the first.**
The first run of this trial flagged 20 disagreements; auditing
them exposed two harness defects: expired (check-by-passed)
bookings still counted as contending, and rows re-committed by
table edits counted as fresh proposals. Both made the shadow
look stricter than its stated rule. The harness was fixed and
re-run; the first run's extra 14 are recorded here as
Jacquard-wrong (harness) rather than silently replaced —
the corrected numbers above are the trial's result, and the
defects are part of its process record.

## Findings

- **F1 (primitive gap):** contention/overlap over committed
  state is inexpressible in the dictionary today. Any real
  deployment of booking-like rules hits this first.
- **F2 (policy gap):** three of six genuine disagreements are
  expressiveness gaps — conditional starts and authority
  priority — not decision errors on either side. A "priority"
  or "conditional" concept is a spec-level decision for Casey,
  not something this trial smuggles in.
- **F3 (incumbent hygiene):** three real double-bookings of
  exclusive seats in six days, one costing a re-plan. The
  incumbent process (a text board + goodwill) has no gate at
  all; even policy/1 alone, without the contention flag, would
  have caught none of them — but a contention sense would.
