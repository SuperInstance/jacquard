# Completeness probes — F1/F2 findings (2026-11-02)

**Question put by Casey (2026-11-02 12:07 AKST):** the Phase 3
shadow trial found three things the system could not express —
interval contention over committed state (F1), conditional
starts and authority priority (F2). Are they first-class
concepts the design is missing, and if the primitives must grow,
what is the smallest addition that closes them? "We don't want
to add any more than we need to."

**Method.** Each gap was tried against an escalation ladder,
cheapest first — (1) policy content in the existing 26
primitives, (2) data carried on the proposal, (3) a lifecycle
machine, (4) a kernel-computed sense with a stated method and
declared read set, (5) one new pure form. Lower rungs had to be
proven insufficient before higher ones were measured. Test
corpora: the real booking-board history the shadow trial used
(its stated window: the first 63 schedule commits of
SuperInstance/agent-inbox, head 0d23fd56 — the live board has
since grown past the snapshot, so the corpus pins that head and
fails loudly if it moves), plus an adversarial synthetic corpus
authored by an independent agent who never saw the candidate
implementations (35 cases, 11 flagged ambiguities).

**Headline.** No new primitives. No new fold sections. F1
closes at rung 4 (one parameterised sense), F2a at rung 2 (one
field on the proposal body), F2b at rungs 2+3+4 (one data
field, transitions on a domain machine, one provenance sense).
The one general form that would also work (a fold/exists over
lists) was built and measured, and loses: ~56× the evaluation
cost, a whole-list rewrite cost on every commit, and a
demonstrated hole in computed effects unless the token walk is
extended first. Details and evidence per probe below; the
minimal set actually implemented is listed at the end.

---

## Probe A — contention (F1)

**The check:** "this interval overlaps a committed interval on
the same resource" — with the board's real rules: same box,
exclusive-seat conflict, same-lane renewals excluded, bookings
whose check-by passed before the candidate starts are dead,
strict overlap (touching endpoints do not contend).

### Rung 1 (policy content in the 26 primitives) — PROVEN IMPOSSIBLE

Three exhibits, all in tests/probes/test_probe_a.py:

1. **Inventory.** The only list-consuming primitives and syntax
   forms are {count, sum, min, max, contains, first, snoc, cat}.
   None yields an element beyond the first; there is no
   tail/index/projection form, and words cannot recurse
   (references must resolve to previously defined words).
2. **First-only counterexample.** A word that checks contention
   against only the first booking of a committed list defines
   cleanly, runs — and answers "clear" on a state where the
   second booking contends. The failure is silent, which is
   worse than a refusal.
3. **No field projection.** `sum` over a list of booking maps
   raises Refusal FIELD; and two states with identical booking
   count (2) and opposite contention labels prove no
   count-based reading can distinguish them.

**Lemma (why no word can do it).** Contention is determined
by the multiset of starts and ends alone — coverage at a point
is a pairing-invariant — so the information is present in
committed state. But computing it requires a *filtered
aggregate*: the count of intervals with start < b and end > a,
i.e. a predicate applied per element and then aggregated.
Against the test-asserted inventory of list consumers
({count, sum, min, max, contains, first, snoc, cat}), no form
applies a predicate per element, none filters, and none
addresses an element beyond the first; and the reference
graph is acyclic, so no word can manufacture iteration by
self-reference. The wall is vocabulary, not information —
which is exactly the shape of gap a sense exists to fill.

### Rung 4 (parameterised contention sense) — WORKS

A sense `contention:<box>/<seat>/<start>/<end>/<producer>/<id>`
whose method states its read set (committed units under
`booking/<box>/`) and its filters (active status only;
different producer — same-producer is a renewal; candidate-id
exclusion; check-by expiry; the board's seat rules; strict
overlap). Its value carries the contender list, count, and the
highest contender rank (Probe C consumes the last two). A
dictionary guard word (`booking-clear`) reads the published
reading; the booking machine's `commit` transition is guarded
by it. The harness computes nothing: overlap lives in the
kernel's projection, the decision in the machine.

Evidence:

- **Real corpus: 52/52 shadow decisions reproduced**, including
  the contender id sets, not just booleans. The three
  incumbent-wrong double-bookings from the trial are all
  caught. Refold of the resulting log reproduces the state
  hash; republishing a reading is byte-identical
  (deterministic under fold).
- **Adversarial corpus: 35/35 exact** (37 candidate decisions
  across the static and temporal cases) — after one correction
  the probe itself forced: the first subject grammar omitted
  the candidate id, scoring 33/35 on exactly the two cases
  resting on "a booking never contends with itself" under id
  reuse. Adding the id as a final subject field (same rung)
  closed both; a gate-by-gate comparison against the fold
  predicate confirms the six grammar fields are exactly the
  candidate fields the reference predicate reads. Two honest
  residues remain, both structural rather than label-visible:
  the sense's predicate is fixed (a future rule variant that
  makes contention depend on a candidate field the grammar
  does not carry needs another grammar field, where a fold
  form would need none), and the positional `/`-joined
  subject would mis-split on a field containing `/` — the
  implementation therefore refuses such field values by name
  (FIELD) instead of misparsing silently.
- **Cost:** median 1.02 ms per reading at 1,000 committed
  bookings on one box (0.011 ms at 10, 0.091 ms at 100) —
  linear in bookings per resource, against a 2.29 ms median
  fold of the full 3,295-entry replay log as baseline. The
  scaling shapes favour the sense as the board grows: its
  cost is per-resource, the fold form's is per-list (every
  booking on every box), so the 56× ratio at 1,000 is the
  *floor*, not the ceiling.
- **Staleness is the sense's one sharp edge, pinned by test:**
  a guard reads the latest *published* reading; commit an
  overlapping booking after publication and the guard still
  answers "clear" until republication. The implementation
  therefore publishes the reading inside the decision step
  (as_of_seq == the decision's own position), never as a
  separate operator action. This is a wiring requirement, not
  a new mechanism.

### Rung 5 (a general fold/exists form) — BUILT, MEASURED, NOT NEEDED

A `{"any": [...]}` quotation form was prototyped (subclassed
evaluator, quarantined in tests/probes/fold_experiment.py). It
works and agrees with the sense on every corpus case. It
loses on three measured grounds:

- **Cost:** 56.9 ms vs 1.02 ms at 1,000 bookings (~56×) —
  per-element evaluator recursion against the sense's single
  pass.
- **Layout tax:** a word can only fold a list it can fetch, so
  bookings must live in one list-valued unit; every commit
  then rewrites the whole list (write value 12,991 bytes at
  100 bookings → 130,891 at 1,000), against a constant 128
  bytes for the per-id unit layout the sense reads.
- **Computed-effects hazard (the decisive one):** with the
  stock token walk, a definition hiding a Tier-E verb inside
  the quotation is accepted with computed_effects == [] while
  its evaluation emits a write per element — a silent breach
  of the C2 property (a word's effects are exactly the union
  over its expansion). The hazard is in the walk, not the
  runtime, and it is fixable (a descending walk catches the
  verb) — but the fix must land in the spec, the checker, and
  the TypeScript conformance port before the form is safe,
  which is a spec-revision programme to buy something the
  sense already provides.

**Verdict A: rung 4.** One parameterised sense + guard words +
a domain machine (the booking machine is a definition, not
kernel code). Nothing added to the primitive set. Two method
details the implementation fixes, both from the adversarial
corpus's flags: the sense's value also reports
`unclassified` — seat strings (the candidate's and committed
rows') that its classification table knows as neither
exclusive nor `detached` — and the profile's `booking-clear`
guard requires that list empty, so a misspelled seat holds
the booking for a human instead of silently clearing (the
sense stays faithful to the stated rules; the fail-closed
check lives in the guard, where a deployment can amend it).
And the determinism claim, stated precisely: readings are
*published values* — refold reproduces state from the log
(same log → same state), and a reading is additionally a pure
function of the entry prefix up to its `as_of_seq` plus its
parameters, so recomputation at that position reproduces it
byte-identically (asserted in the probe). Publication in the
booking flow is unconditional on the decision's outcome: a
denied booking still leaves its reading in the record, as an
audit artifact; readings never feed the sense's own read set,
so they cannot compound.

---

## Probe B — conditional starts (F2a)

**The concept:** "starts when X lands" — the REBOOK row whose
occupancy was event-driven and unknowable to the shadow.

### Rung 1 (submit-when-it-fires, the incumbent pattern) — WORKS AS MECHANICS, FAILS AS A RECORD

Scenario S6 demonstrates the failure mechanically: an external
watcher polling state and submitting when X lands produces the
execution — and the log cannot answer either audit question.
Before the start, no entry names the pending intention ("what
are we waiting for?" is unanswerable, and nothing can expire
it); afterwards, any reason the watcher writes into its own
submission is an unchecked claim by the watcher, not a fact
the record verified ("why did this start?" has only the
watcher's word for it). The insufficiency is not that the
eventual decision lacks a string — it is that the *waiting*
exists nowhere in the record, so it cannot be listed, expired,
or audited. The concept lives only in the watcher's head.

### Rung 2 (a wait-condition carried on the proposal) — WORKS

The proposal body carries `wait: {"guard": <word name>,
"deadline_seq": <int>}`. The guard is an ordinary pure
dictionary word over committed state (signature map->bool,
computed effects empty — validated before anything is
appended, reusing the machine checker's guard rules). A
wait-conditioned proposal whose guard is false enters the
decision queue with the wait spec on its decision entry — the
fold already copies whole decision bodies, so **no new fold
section exists**; the nine sections stay nine. On each new
commit the sequencer re-evaluates outstanding wait guards
(the "pump"); true releases through the existing release path,
an expired deadline through the existing expire path. If the
guard is already true at submission, the proposal takes the
normal path and nothing is queued.

Scenarios (tests/probes/test_probe_b.py, 13 tests, all pass):
X lands → start; X never lands → expire at deadline; X lands
twice (exactly one execution); two waiters on the same X
(both released, in queue order); condition already true at
submission (immediate, nothing appended); audit reconstruction
from the log alone (queueing decision names the guard, the
landing entry precedes the release, the release names the
proposal).

**Semantics pinned — state-based, not edge-based (S3b).** The
guard reads current committed state at re-evaluation time. If
X lands and is retracted by compensation *before* the next
re-evaluation, the waiter does not start; a later re-landing
starts it. "Landed once, historically" is not the condition;
"is landed, now, in committed state" is. This matches the
system's nature (state is a fold; there are no edges to
remember that the fold has not kept) — and it is the safer
reading for the board's case: a compensated landing *should*
not trigger starts.

**Ordering rules the slice specifies** (each measured or
pinned in the probe; stated here because re-evaluation is
where event-driven systems quietly diverge):

- The pump runs *after* the triggering commit is folded,
  against the resulting committed state — a guard never reads
  a half-applied commit.
- Guard-true beats deadline at the same log position: expiry
  exists to bound waiting for a condition that does not hold,
  so a condition that holds in current state releases even
  past its deadline.
- The pump iterates to fixpoint within the commit step,
  including releases that themselves commit (waiter chains
  complete in one step); each pass strictly reduces the
  waiter count or stops, so it terminates.
- A guard that *refuses* during re-evaluation (purity is not
  totality — a guard can raise on a state shape it did not
  anticipate) is treated as not-true for that pass, and the
  refusal is itself recorded: a re-queueing decision entry
  carrying the same wait spec and the reason
  `wait-guard-refused:<name>`. A raising guard can neither
  crash an unrelated submission nor fail silently.
- Supersession: the queueing decision records the wait; the
  release decision (which carries `releases`) supersedes it
  for disposition. Record scoring already treats the first
  decision per proposal as primary and release decisions as
  follow-ups; the spec says so out loud.

**Two things the slice must specify (measured in the probe):**

- *Deadline accounting.* Queueing a waiter appends 5 entries
  (decision + lifecycle transitions), so an absolute
  `deadline_seq` is partly consumed by the act of queueing.
  The slice keeps the probe's pinned reading — the deadline
  is an absolute log position and queueing's own entries
  count toward it — because it is the simpler spec sentence
  and S2 was written and measured against it. Producers
  computing a deadline from "current length + N" should know
  N includes the queueing entries; the spec says so.
- *Composition with policy queueing.* The probe's waiter used
  only `write` (policy: allow). If a wait-conditioned proposal
  also carries protected effects, two release authorities
  exist. The slice composes them in order: the wait guard
  gates *when the proposal is decided*; when it fires, the
  proposal goes through the ordinary policy decision fresh —
  allow executes, queue becomes an ordinary approval item
  (the wait is spent), deny refuses. Guard release never
  bypasses the policy gate.

**Verdict B: rung 2.** One body field + sequencer wiring
(validate the guard at submission; re-evaluate after commits,
re-entrancy-safe). No new primitives, no new fold section, no
new machine (the proposal machine already has the tentative
state the waiter sits in).

---

## Probe C — authority priority (F2b)

**The concept:** a Casey-directed booking overrides contention
— trial disagreement 5, where the shadow would have queued a
captain's booking behind an ordinary one. The probe decomposes
it before building, per the charter:

### (i) Rank = rung 2 (data)

The proposal carries a rank; the committed booking record
stores the **effective** rank — `min(asserted, ceiling)`, and
0 with no grant — plus the asserted rank beside it, so the
record never launders a claim into a fact. Nothing about rank
needs evaluation power: it is carried, hashed, replayed.

### (ii) Recognition = rung 4 (an authority sense) — because the gate cannot see write targets

A grant ("producer X may assert rank up to N") must be
*recognised by the record*, and the obvious storage — a unit
`authority/<producer>` — is writable by anyone. Could a
better policy refuse non-operator writes under `authority/`?
No — and this is structural, not a policy/1 oversight: the
gate's inputs are (producer, kind, *effects*, record,
standing). Effects are coarse verbs; a `write` effect does
not carry its target unit, and no dictionary word can gate a
submission (words are evaluated by machines and flows, never
by the gate). Target-based write gating is therefore
inexpressible at rung 1 for *any* policy version that keeps
the gate's current input vocabulary — widening that
vocabulary would be a kernel change of the same order as the
sense, with a larger blast radius (every decision would
depend on body inspection). The probe's mandatory self-grant
attack (C5) shows the consequence and the fix in one test:
Mallory's own proposal writes `authority/mallory = 99`, the
write **lands** (the unit is 99 in committed state) — and the
authority sense still reports her ceiling as null, because
its method counts only grant writes that satisfy all three
filters: entry kind `execution`, entry producer `operator`,
and an applied write to the unit `authority/<producer>`.
Ceiling resolution is last-wins: a later operator grant
replaces the ceiling, so a lower re-grant is a downward
revocation. Her rank-9 override then fails exactly as an
ungranted one (C4). Provenance comes from the log, not from
the value's current holder. One honest limit: the sense is
the only *sanctioned* reader of `authority/` — a future word
that reads the raw unit directly would see the attacker's
99. The profile never does this (its words consume the sense
only), and the spec states that the unit value alone is not
evidence of a grant; making it a mechanism rather than a
convention would require the target-aware gate rejected
above.

### (iii) Override = rung 3 (machine transitions + records)

Preemption is executed as ordinary operator proposals (class
`preemption`) that write the loser's booking record to status
`preempted` and write a `preemption/<loser>` record naming
{winner, winner_producer, rank, authority_sense, at_seq}; the
loser's booking-machine instance is stepped with event
`preempt`, and a queued loser is rejected from the decision
queue (its write never executes — asserted in C2). No kernel
writes were invented: the entire override replays from
ordinary entries through the ordinary policy gate.

Evidence (tests/probes/test_probe_c.py, 8 tests, all pass):

- **C1, override of an ACTIVE booking:** audit replay from the
  log alone reconstructs the whole event —
  `{winner: W, winner_producer: captain, rank: 5,
  grant_seq: 19}` — with ordering proven: the grant entry
  precedes the decision point, which precedes the preemption
  execution. "Who overrode whom, by whose authority, what did
  it cost" is answerable from the record; the cost is the
  loser's lost interval, in its preempted record.
- **C2, override of a QUEUED booking:** the loser is disposed
  by the winner's commitment (rejection + preemption record +
  machine transition), and zero execution entries exist for
  its proposal — a queued booking preempted before release
  leaves no effects behind.
- **C3, tie:** see below.
- **C4, unrecognised rank:** asserted 9 with no grant →
  effective 0, ordinary contention, no preemption; the
  proposal body preserves the assertion next to the effective
  value.
- **C5, self-grant attack:** above.
- **C6, grant ceiling:** asserted 5 under a ceiling of 2 →
  effective 2; preempts a rank-1 incumbent, does not preempt
  a rank-3 one. (The probe caught a contradiction in the
  coordinator's own staged brief — a binary granted/not
  definition of effective rank in one paragraph, a ceiling in
  the scenarios. The ceiling is the semantics; the binary
  predicate survives separately as `rank-granted`. Recorded
  here because the process record is the point.)

### The tie — a deliberate deviation from the charter's letter

The charter asked for "rank tie → named refusal, no silent
winner." The probe implements: the challenger is **queued**
under a taken machine transition whose event is `tie` and
whose guard is `booking-tied`; the published contention sense
names the equal-rank contender; the incumbent is untouched.
"No silent winner" is fully satisfied. It is not a refusal —
and on the evidence, it should not be: a tie is two legitimate
authorities in conflict, which is precisely the class of item
Casey's standing ruling sends to the batched decision queue
("batch items for the boss's decision while all other work
continues"), not a malformed or unentitled submission, which
is what refusals are for. The implementation names the
outcome in the record: the tie is a taken transition entry
(event `tie`, guard `booking-tied`) in the challenger's
lifecycle, the published contention sense names the
equal-rank contender it tied with, and the operator CLI
annotates such queue items as authority ties in the boss's
batch. The interim disposition is stated, not left implicit:
**the incumbent holds the interval while the challenger
waits** — "no silent winner" means no *unrecorded* winner;
the status quo proceeding under a fully recorded challenge,
pending the boss's batch, is the disposition Casey's ruling
implies, and the alternative (freeze both) would let any
equal-rank filing halt a running booking, a denial-of-service
the board does not want. If Casey prefers ties to bounce, a refusal
name is a one-line spec addition; the behaviour difference is
queue-vs-bounce, and the probe's C3 pins the queue behaviour
either way.

**Verdict C: rungs 2+3+4 in combination** — rank as data, an
authority sense for provenance, machine transitions for the
override itself. No rung-5 question arises: nothing in
authority priority needs new evaluation power.

---

## The minimal set (implemented as spec 0.3)

Added to the system — the complete list:

1. **Two built-in senses** (rung 4, kernel projections, spec
   §11): `contention` (parameterised by box/seat/start/end/
   producer/id; method and read set as probed; value carries
   the contenders, count, max_rank, top_id, and any
   unclassified seat strings; field values containing `/`
   are refused FIELD where the name is constructed) and
   `authority` (subject = producer; the three-filter,
   last-wins method Probe C states). Sense-computation
   vectors join the golden vectors (state fixture + subject →
   expected reading); the TypeScript checker declares sense
   computation out of its fold scope (SKIP, stated in its gap
   report).
2. **One proposal-body field** (rung 2): `wait: {guard,
   deadline_seq}` — guard validated before anything is
   appended (exists, map->bool, pure); false at submission →
   queued with the wait spec on the decision entry (no new
   fold section; a refold test pins the nested spec's
   survival); true → normal path. On each commit the
   sequencer re-evaluates outstanding wait guards under the
   ordering rules Probe B states (post-fold evaluation,
   guard-true beats deadline, fixpoint within the step,
   refusing guards recorded not swallowed); a fired guard
   sends the proposal through the ordinary policy decision
   fresh — allow executes, queue becomes an ordinary
   approval item with the wait spent, deny refuses — with
   `wait-satisfied:<guard>` among the reasons; an expired
   deadline expires the item with reason
   `wait-expired:<guard>`. To carry those reasons,
   `release_queued` / `reject_queued` / `expire_queued` gain
   an optional reason parameter (defaults unchanged). The
   parameter is the channel, not a luxury: the decision
   entry is written by those functions, so a reason a caller
   needs on the entry can only arrive through them.
3. **A booking profile shipped as definitions, not kernel
   code** (rungs 2+3): the booking machine, the guard words
   (`booking-clear`, `booking-contended`, `booking-outranks`,
   `booking-tied`, `rank-granted`, `effective-rank`,
   `rank-below`), and the live flow with preemption (operator
   proposals, class `preemption`) — as a profile module
   beside `lifecycles.py`, with the booking record schema
   (rank + asserted_rank) stated in the spec as an
   application profile. The operator CLI marks wait items
   and authority ties in the queue listing. The seven words
   are dictionary definitions — the system's free currency
   (inventing terms is free; inventing effects is what costs)
   — so the kernel surface of this whole phase is items 1–2;
   the words compose from each other and the primitives and
   are counted here only for completeness. The two senses
   are kernel-resident because senses are the spec's only
   mechanism for kernel-computed readings: a profile cannot
   register one by definition (words cannot iterate the entry
   stream either — that was Probe A's lemma), so a
   "profile-defined sense" would still be trusted code, just
   worse placed.

**Not added:** any primitive (the count stays 26 + 9 syntax
forms); any fold section (still nine); any refusal name; any
entry kind. The spec version moves to 0.3 because wait
changes what a conforming sequencer does with a decision
body — a behavioural change the seal should say out loud —
and vectors/fixtures regenerate accordingly, as they did for
0.2.

## Residuals — what remains genuinely inexpressible or unbuilt

- **Zero-duration bookings.** The strict formula counts an
  interior point as contended (adversarial corpus, flagged by
  its author). Whether a point booking is an interval is a
  rules question for the board protocol, not a mechanism gap;
  the sense implements the formula as stated.
- **Spelling is case-exact, and unlisted seats now fail
  closed.** `claude_code` ≠ `claude-code` and `Lane-A` ≠
  `lane-a` remain true (canonical values are the producers'
  contract; the kernel does no normalisation). What changed
  during this phase: an unlisted seat string previously
  cleared *silently*; the sense now reports unclassified
  seats in its value and the profile guard holds such
  bookings for a human (Probe A verdict). The residual is
  narrower than the trap was: a *producer* typo (`Lane-A`)
  is indistinguishable from a genuinely different producer —
  that is identity discipline, not vocabulary, and stays a
  residual. The board protocol should still carry its seat
  list so deployments can extend the guard's table.
- **Partial contention does not exist.** A check-by expiring
  mid-window still contends for the whole window; the model
  is whole-window or nothing, as the board's rules are.
- **Duplicate ids across producers** are excluded by the id
  rule but remain corrupt data the kernel cannot distinguish
  from a legitimate re-presentation; the corpus's real ids
  are board-key-derived and unique. Provenance of identity
  is a producer-discipline matter (GAP-3's neighbourhood).
- **State-based conditions have a blind interval.** A land
  and a retract inside one commit batch are never observed
  as landed (Probe B). Documented semantics, accepted.
- **The fold form remains the documented future option** if
  collection predicates proliferate beyond senses' reach —
  its preconditions are now known exactly (descending token
  walk in spec + checker + TS port, and a list-layout
  decision). One sense per domain question is the proven
  first resort; senses are cheap to add precisely because
  each is small, stated, and separately testable.
- **Downstream-value attribution** (GAP-1) is untouched by
  this phase, as is the rest of §5.2 of the design record.

## Process record

- The adversarial corpus was authored independently (labels
  derived from the trial's stated rules only); it caught a
  wording ambiguity in this phase's own brief (the
  back-to-back case) and 10 further ambiguities in the rules
  themselves, all preserved in tests/probes/
  adversarial_a_notes.md — several became the residuals above
  rather than being smoothed into labels.
- The live board outgrew the trial snapshot during the phase
  (the Phase 2/3 DONE rows and this phase's own booking); the
  corpus pins the trial's window head and asserts it.
- Probe A's first subject grammar scored 33/35; the fix was
  found by reading the two failures, not by weakening a test.
  Probe C caught a contradiction in the coordinator's staged
  brief (binary vs ceiling rank) and implemented the ceiling.
  Both are recorded in the probes' reports and in this
  document's Probe C section.
- Scope limit of the 35/35 claim, stated plainly: the
  adversarial corpus inherits the trial's stated rules (its
  author worked from them), so it cannot catch a rule the
  trial itself got wrong. The residuals above — zero-duration
  points, vocabulary, partial contention — are exactly that
  class: places where the rules, not the mechanism, are the
  open question.
- A DeepInfra critique pass over this draft (DeepSeek-V4.1-
  Flash, ~4,000 completion tokens) landed several blows that
  changed the document and the implementation set: the wait
  ordering rules (post-fold evaluation, guard-true beats
  deadline, fixpoint scope, refusing-guard disposition,
  decision supersession) were unspecified in the first draft
  and are now pinned in Probe B; the authority sense's method
  gained its three-filter statement and last-wins ceiling
  resolution, and Probe C(ii)'s justification was rewritten
  from "rung 2 is attackable" to the target-blindness of the
  gate; the tie's interim disposition (incumbent holds) is
  now stated rather than implied by "no silent winner"; the
  seat-vocabulary fail-closed check entered through the
  critique's "mislabelled residual" charge; the determinism
  wording for published readings was split into its two true
  halves. Criticisms considered and not adopted, with
  reasons in place: trimming the guard-word count (words are
  definitions, the free currency — the kernel surface is
  unchanged either way) and relocating the senses into a
  profile (no spec'd mechanism lets a profile register a
  sense; it would be trusted code either way, worse placed).

---

## Addendum — what Phase 5 can rely on (2026-11-02)

Written at the parent lane's request: Phase 5 (beachhead 1 — a
live adapter to a real coding agent, the network service,
batched queue notifications, a measured proof run) starts from
this document. The per-gap verdicts, stated once more in
adapter-facing terms:

| Gap | Winning rung | The surface Phase 5 builds against |
|---|---|---|
| F1 contention | 4 — kernel sense | The `contention` sense (spec 0.3 §11): parameterised readings, published in the log with `as_of_seq`, consumed by guard words. An adapter mediating a contended resource publishes/consumes readings; it never computes overlap itself. |
| F2a conditional starts | 2 — proposal data | The `wait: {guard, deadline_seq}` body field (spec 0.3), with its pinned ordering rules: post-fold re-evaluation, guard-true beats deadline, fixpoint pump, refusing guards recorded. A fired guard re-decides through policy — a wait is a timing gate, never a policy bypass. |
| F2b authority priority | 2+3+4 — data + machine + sense | `rank`/`asserted_rank` as record data, the `authority` sense (operator-only provenance, last-wins ceilings) for recognition, and profile machine transitions (`preempt`, `tie`) for the override itself. An adapter expresses priority as data and surfaces asserted vs effective rank distinctly; it does not carry its own priority flags. |

Other surfaces the adapter may treat as stable at spec 0.3:
the envelope submission path and its verdict vocabulary
(accepted / REFUSED-by-name / decided with outcome); the
batched decision queue with hash-bound approvals (the slice-10
CLI semantics — an approval binds the queued decision's hash,
and a changed item fails approval); machine lifecycle
transitions as the audit trail for anything the adapter
drives; senses generally — published readings with stated
methods, never bare numbers; the §13 decision-model provider
seam, advisors only (a decision model may publish readings;
it never gates).

Non-reliances, stated so Phase 5 does not plan on them: there
is still **no network service** (Phase 5 slice 13 builds it —
the kernel is a library and a CLI); the booking profile is
the only shipped domain profile, so the coding-agent adapter
authors its own machine/word definitions against the profile
checker, as the booking profile did; and contention readings
are computed by the kernel that owns the record — an adapter
on a second machine consumes the service's published
readings, it does not recompute them.

## Addendum — the `any`-quotation hazard is closed (2026-11-02, Phase 6 slice 17)

Appended, not rewritten: the findings above stand as written,
including probe (f)'s verdict at the time — the rung-5 fold
form was rejected, and the hazard it exposed was recorded as
a spec-level hole. Spec 0.4 (sections 4–5) closes it:

- The token forms are exactly `{"lit"}`, string, and
  `{"if"/"else"}`. A dict token of any other form is
  REFUSED(SPEC) at definition time, with the form's key named
  in the refusal detail.
- The effects walk descends into every token position of
  every form — both if branches, any nested form's body —
  except inside a literal's value, which is data: this
  language has no form that evaluates data as code, so the
  exclusion cannot become an evaluation path.
- C2 is stated in section 4 with the quotation case
  included: a word's computed effects are the union over its
  expansion, and a quotation form, if a future version
  defines one, has its quoted body accounted at definition
  time. Quotation defers evaluation, never accounting.

Consequences, verified in the suite: through the stock kernel
the probe's `any-write` definition is REFUSED(SPEC) naming
`any`; through the quarantined `FoldDictionary` the same
definition is accepted with computed effects `["write"]` —
accounted even in the extension, because the prototype now
inherits the descending walk. The two probe-(f) tests that
pinned the hazard's existence are re-aimed at the closure as
declared supersessions (their docstrings say so), and the
acceptance battery is `tests/test_quotation_battery.py`:
the original case both ways, nested quotations, a quotation
inside an if branch, smuggling via definition composition,
hybrid dict forms, verb-shaped data inside a literal (inert),
and a forged body refused on the evaluation path. The TS
conformance position is recorded in `conformance/ts/
GAPS.md` item 17: definitions remain SKIP in the fold-scope
checker, with the 0.4 accounting rule stated for the future
evaluator implementer.
