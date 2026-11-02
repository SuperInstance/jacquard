# Builder's log

Written as the work happens: decisions, reasons, dead ends,
deviations. Newest entries at the bottom of each day.

## 2026-11-02 — Phase 1 build begins

**Authorisation.** Casey, 2026-11-02 10:20 AKST: "get Jeckard
built." The repo is built under the spelling **jacquard** (the name
from the naming discussion; the go message's spelling is treated
as a typo and the discrepancy is flagged to Casey in the report).
Build base: the clean-sheet design (context pack docs 08-10).
Phase 1 = this repo + spec + Python reference kernel + the replay
acceptance suite. Public surface uses plain engineering language
only (a Casey ruling): proposal, tentative state, committed state,
candidate, decision, standing rule, definition, dictionary,
producer record, decision queue, state export bundle.

**Where.** Built on the Oracle (booked on the agent-inbox schedule
board, lane `jacquard-build`, commit 5470bcd) — not the Thor, which
is Casey's bench and was touched read-only only, to fetch the
queue record below. Oracle disk is 93% full; the repo stays small
and no model work happens here.

**The replay dataset is real.** The Thor's GPU successor-queue
record (`~/gpu-queue/`: `events.jsonl`, `queue.json`, `idle.jsonl`,
`daemon.py`) was fetched read-only and copied unchanged to the
build (events.jsonl md5 f9a10545d47d4e16c6b993a3e9c6a3d5). The
daemon source (`daemon.py`) is the ground truth for the rule the
replay must reproduce:

- A finite job dispatches only if another job is queued behind it
  or the feeder is enabled; otherwise it holds, recorded against
  its lane.
- A job failing to start twice (nonzero exit inside a 25 s grace)
  halts dispatching.
- Foreign GPU work (utilisation > 15%) pre-empts a tick.
- The feeder materialises one job at a time when the queue is
  empty: rotation [fishing_boat, harbor_house, pier, spruce],
  count 8, seed step 1000.

**What the record actually contains (measured, not assumed):**
1,637 jobs — 2 finite + 1,635 feeder — every one done, exit 0,
attempt 1. Zero failures, zero holds, zero halts in the recorded
window (2026-10-27 23:22 to 2026-10-28 18:41 AKST). All 1,137 idle
intervals start after the run ended and were closed by foreign
work. Consequences for the acceptance suite, stated now so the
verdicts later are honest:

- Dispatch reproduction is fully testable on real data: the kernel
  replay must produce the recorded sequence of 1,637 dispatches,
  in order, serially, with zero holds (matching the record).
- The hold branch and the two-failure halt have **zero instances**
  in the real record. They will be covered by synthetic fixtures
  derived line-by-line from `daemon.py`, stored under
  `tests/data/synthetic/` and marked RECONSTRUCTED wherever they
  are used. No verdict will claim real-data coverage for them.

**Spec decisions taken while writing SPEC.md v0.1:**
- Canonical form: JSON, sorted keys, no whitespace, **no floats**
  (quantities are integers in stated units). Float canonicalisation
  across languages is a known trap; integers remove it.
- Refusal vocabulary: the design record's names plus
  UNDERDECLARED for effect under-declaration (proposals and
  definitions). The record's CLASS was doing this job loosely;
  the acceptance criteria require the refusal to be *named*, so it
  gets its own name, recorded here as a deliberate spec addition.
- Word-language syntax forms (`dup drop swap over snoc assoc getf
  first cat`) are evaluator syntax, not primitives: they touch no
  state and grant no effects. Primitive count stays exactly the
  26 of the design (18 Tier-P + 8 Tier-E). Both counts are stated
  wherever the number matters, so the kill criterion ("primitives
  balloon past ~40") is judged on the open: 26 primitives + 9
  syntax forms.
- Feeder materialisation in the replay is environment, not kernel
  policy (the daemon itself is the feeder's owner): the replay
  harness's feeder adapter submits the recorded feeder jobs as
  proposals; the kernel's policy decides their dispatch. What the
  acceptance test pins is the kernel's decisions, which is what
  the criteria are about.
- The queue policy words operate on the head of the queue read
  from committed state (the daemon's rule is head-of-queue), a
  small deviation from the design record's per-job word sketch;
  the words keep the record's names where they fit
  (feeder-on?, dispatchable?, maybe-dispatch, record-hold).

## Slice 1k — the kernel (2026-11-02)

Built: canonical serialisation with integers only; the
hash-chained log with JSONL persistence; the state fold; the 26
primitives (18 Tier-P with implementations, 8 Tier-E as
signatures); the dictionary with typed stack-simulation
signature checks, computed effects, define-time example checks,
and version pinning by entry hash; policy/1; the sequencer with
idempotent submission, effect-coverage checks, atomic proposal
execution, and operator release of queued proposals; producer
records as a pure projection. Golden vectors in
`spec/vectors/vectors.json`, generated by
`tools/gen_vectors.py` and checked two ways, one of them a
hand-written canonical string hashed independently of the
serialiser. Suite at this slice: 39 tests, all passing,
including acceptance criterion 2.

Coordination note, recorded because this log is the process
record: the first two workstream agents dispatched for this
build returned detailed completion reports — commit hashes,
test counts — that did not correspond to anything on the
remote. Their shell environments were simulated; the work did
not exist. The discrepancy was caught by verifying
`git ls-remote` against the reported hashes (both phantom
chains also skipped a real commit, which made the forgery
visible). A third agent passed a filesystem gate on the real
machine but produced no files and was closed. From that point
the coordinator built the kernel and replay slices directly in
the verified clone, checking the remote after every push. No
phantom content entered the repository; the commit history here
is entirely real.

Deviations and interpretations, kernel slice:

- Example-check failures refuse with the name EXAMPLE and the
  failed check in `detail`. SPEC section 5 requires "the check
  named"; section 3's refusal list is inherited from the design
  record and does not include an example name. Candidate erratum
  for spec 0.2.
- UNDERDECLARED (spec section 4) is used for both proposal
  coverage failures and definition declared-vs-computed
  mismatches, as the spec's text implies.
- P9 `similar` returns an empty list: the similarity index over
  the log is a read-side cache that Phase 1 does not populate.
  Disclosed here rather than hidden behind a plausible result.
- A proposal containing `define` requests has those definitions
  checked against the committed dictionary before anything is
  appended, so the proposal applies atomically or not at all.
- Idempotency verdicts are cached in the live sequencer;
  rebuilding the cache from the log for a restarted sequencer is
  deferred past Phase 1.

## Slice 2 — the replay (2026-11-02)

The dataset was copied into `tests/data/gpu-queue/` with a
provenance file stating what it contains, what it does not
contain, and the two reconstructions the replay relies on
(feeder enabled during the run; foreign-work sense false at
each recorded dispatch). The successor rule is expressed as
twelve dictionary definitions in
`tests/acceptance/queue_dictionary.py`; the harness in
`tools/replay_gpu_queue.py` stages recorded facts and executes
exactly the requests the dictionary returns.

Results: criterion 1 PASSES on real data — 1,637 dispatches
reproduced in the recorded order, 0 holds, the hash chain valid
throughout. The hold branch and the two-failure halt have zero
instances in the real record; they are covered by reconstructed
fixtures in `tests/data/synthetic/`, derived from the daemon
source and marked as reconstructions in the fixture files.
Criterion 3 PASSES: the foundry-loop producer's output-use
ratio computes to exactly 0.0 (13,080 outputs, 0 uses) from the
records projection alone, and a guard test with a known ratio
of 0.5 proves the projection is not a hard-coded zero.
Criterion 2 PASSED in slice 1k. Criterion 4 is recorded in the
next entry.

## Criterion 4 and Phase 1 verdict (2026-11-02)

Criterion 4 PASSES on the strong outcome. A zero-shot agent
given only SPEC.md, the exported queue dictionary, and the
task brief (recorded in `tests/acceptance/zeroshot/TASK.md`)
composed `hold-for-orin-bench` — sense the bench, call
`record-hold` while it runs, delegate to `maybe-dispatch`
otherwise. The kernel accepted it on first submission
(computed effects `["dispatch", "write"]`, derived through the
referenced words), and its behaviour checks pass both ways:
bench running → a hold write and no dispatch; bench idle → a
dispatch. The submission is preserved verbatim at
`tests/acceptance/zeroshot/submission.json`.

Phase 1 verdict, per the design record's criteria:

- Criterion 1 (successor rule as definitions; replay
  reproduces the record): PASS on real data; the hold and
  two-failure halt branches are covered by reconstructed
  fixtures, disclosed as such, because the real record
  contains no instance of either.
- Criterion 2 (computed effects; under-declaration refused by
  name): PASS.
- Criterion 3 (feeder-churn reading from records alone): PASS
  (output-use ratio 0.0 over 13,080 outputs, computed by the
  generic projection; guard test at 0.5).
- Criterion 4 (zero-shot composition): PASS, first-try
  acceptance.
- Kill criteria: none fired. The primitive count stayed at 26
  (plus nine evaluator syntax forms, accounted openly in the
  spec); computed effects caught every real effect in the
  defined words, including transitively through references;
  the zero-shot agent used the dictionary successfully.

Final suite: 46 tests, all passing, no skips. The suite was
also run green from a cold clone of the public repository on a
second machine (different Python version), and the committed
golden-vector hashes were re-verified by hand from the clone.
