# Probe A adversarial corpus — labelling notes

**Author role:** independent corpus author for Jacquard Phase 4, Probe A.
**Independence:** no candidate implementation was consulted (none was
looked for) and no implementation code is included. Labels derive
strictly from the reference rules stated in the Probe A brief, which
match the published shadow-trial semantics (`tools/shadow_trial.py`,
`docs/shadow-trial-2026-11-02.md` in this repo at v0.2.0).
**File:** `tests/probes/adversarial_a.json` — 35 cases (33 static
shape-(a) cases, 2 ordered-event shape-(b) cases), 11 recorded
ambiguities. Times are small integer minutes (base 1000); box is
`thor` unless the case is about box identity. Every booking uses only
the canonical schema fields.

## The rules as applied

A candidate C is contended by a committed booking O iff **all** of
the following hold; the expected `with` list is every such O, sorted:

1. `O.id != C.id` — a booking never contends with itself.
2. `O.producer != C.producer` — exact string comparison. Same-producer
   overlaps are renewals, never contention.
3. `O.box == C.box` — contention is per-box.
4. `O.status == "active"` — `done`, `cancelled` and `preempted`
   bookings are inert.
5. NOT (`O.checkby` is not null AND `O.checkby < C.start`) — a
   committed booking whose check-by passed strictly before the
   candidate starts is dead by protocol. Equality
   (`checkby == C.start`) is **not** expiry. Only the committed
   booking's check-by is consulted, and only against the candidate's
   start.
6. `seats_conflict(C.seat, O.seat)`:
   - seats equal → conflict iff the seat is in
     {`zcode`, `mcode`, `claude-code`, `gpu`, `stage`, `kimi`, `box`};
   - seats differ → conflict iff either seat is `box`;
   - otherwise no conflict. In particular `detached` contends only
     with `box`, and two different exclusive seats (e.g. `gpu` vs
     `zcode`) do **not** conflict.
7. Strict interval overlap: `C.start < O.end AND O.start < C.end`.
   Touching endpoints (`C.end == O.start`, `C.start == O.end`) do
   **not** contend.

Rank is never consulted: Probe A ignores rank entirely (preemption
by rank is Probe C's concern). A case with committed rank 5 and
candidate rank 0 is therefore labelled contended.

For temporal (shape-(b)) cases, events apply in order: a `commit`
adds a booking, a `status` event changes a committed booking's
status, and each `candidate` event is labelled against the committed
set as it stands at that point in the sequence.

## Ambiguities found (never guessed — labelled per strict reading, flagged)

The same 11 entries appear in the JSON's `ambiguities` array.

1. **Back-to-back coverage wording** (`back-to-back-touching-neighbours`).
   The brief's line "three back-to-back bookings [0,10),[10,20),[20,30)
   with candidate [10,20) — touching both neighbours, no contention"
   does not state the middle committed booking's identity. An
   independent different-id, different-producer middle booking with
   an identical window would contend under the identical-windows
   rule. The case is constructed so the middle row carries the
   candidate's own id (excluded by rule 1) and both neighbours merely
   touch; the label follows the strict formula under that reading.
   Under the other reading the label flips — this is the one case
   where the brief itself under-determines the answer.
2. **Zero-duration candidate** (`zero-duration-candidate-inside-booking`).
   A point at t=1100 strictly inside [1000,1200) satisfies both strict
   inequalities (1100 < 1200 and 1000 < 1100), so it is labelled
   contended. Whether a zero-length "interval" is an interval at all
   (half-open [t,t) is the empty set) is nowhere addressed.
3. **Zero-duration committed booking**
   (`zero-duration-committed-inside-candidate`). Same question,
   mirrored: labelled contended per the strict formula.
4. **Seat spelling** (`seat-spelling-claude-code-vs-claude_code`).
   No normalisation of seat names is specified. `claude_code` is not
   string-equal to `claude-code` and is not itself in the exclusive
   set, so the strict label is no contention — see the
   operator-surprise section below.
5. **Duplicate id** (`duplicate-id-different-producer-excluded`).
   Rule 1 treats id as identity, so a committed row reusing the
   candidate's id is excluded even when every other field differs.
   Whether that row is the same booking, a stale copy, or corrupt
   data is unspecified.
6. **Producer string identity**
   (`producer-case-variant-counts-as-different`). No case-folding or
   trimming is specified, so `Lane-A` vs `lane-a` are different
   producers and the overlap is contention, not renewal. If board
   practice treats producer names case-insensitively, the intended
   label flips.
7. **Check-by inside the candidate window**
   (`checkby-expires-mid-candidate-still-contends`). Expiry is
   tested only against the candidate's start, so a booking dying at
   its check-by mid-window contends for the whole window. The
   formula's label is unique, but partial contention is inexpressible
   and protocol intent for the post-check-by portion is undetermined.
8. **Candidate's own fields (global).** The formula never requires
   the candidate to be `active`, and ignores the candidate's own
   check-by and rank. This corpus assumes candidates are live
   proposals with status `active`; for a non-active candidate the
   stated rules determine no label.
9. **Negative durations (global).** Bookings with `end < start` are
   unaddressed; the formula evaluates mechanically but their meaning
   is undefined, so no such case is included.
10. **Temporal auto-commit (global).** The rules do not say whether
    a decided candidate joins the committed set for later candidates
    in the same event sequence. Both temporal cases assume it does
    not — only explicit `commit` events add bookings. Under
    auto-commit, second-candidate labels could change.
11. **Open seat vocabulary (global).** Any seat string outside the
    exclusive set and not `box`/`detached` is silently non-exclusive,
    including against itself and including typos of exclusive seats.
    Labels are determined, but nothing validates that a seat name is
    canonical, so misspellings degrade silently to no-contention.

## Labels a board operator would probably find wrong (labelled per rules anyway)

Surfaced deliberately for the findings doc; none of these was
smoothed over, and none is ambiguous — the rules are clear and the
outcome is arguably wrong for operations:

- **`seat-spelling-claude-code-vs-claude_code`** — no contention.
  A hyphen/underscore typo silently frees an exclusive seat; the
  double-booking the gate exists to catch walks through.
- **`different-exclusive-seats-gpu-vs-zcode`** — no contention.
  Two exclusive-seat bookings with identical windows on the same box
  do not contend, because exclusivity is per-seat. Correct per the
  rules, but an operator thinking "one heavy seat at a time per box"
  would expect a queue.
- **`same-nonexclusive-seat-observer`** — no contention. Any
  invented seat name is a free-for-all, even against itself.
- **`checkby-expires-mid-candidate-still-contends`** — contended for
  the full window although the committed booking is protocol-dead
  for its second half.
- **`zero-duration-*` cases** — contended. A zero-length marker
  blocks (or is blocked by) a real booking under the strict formula.
- **`rank-ignored-high-rank-committed-low-rank-candidate`** —
  contended. Probe A deliberately has no notion that rank should
  matter here; that judgement belongs to Probe C, but an operator
  reading this corpus alone may find a rank-0 candidate queueing
  behind a rank-5 booking (or vice versa) surprising.
- **`expired-checkby-with-real-overlap`** — no contention. Correct
  by the board's own protocol (an expired booking's seat is
  takeable), but the windows genuinely overlap; anyone reading raw
  intervals without the check-by rule will misread this label.

## Method note

Labels were produced by hand from the rules above and then
machine-checked with a throwaway script (kept outside the repo, not
part of this deliverable) that re-encodes the same reading of the
rules and verifies every `expected` block, including a sequential
simulation of the two temporal cases. The checker validates the
corpus against *this* reading of the rules; it is not, and must not
be mistaken for, the implementation under test.
