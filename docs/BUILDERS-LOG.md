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

## 2026-11-02 — Phase 2 build begins

**Authorisation.** Casey, 2026-11-02 10:57 AKST: "continue work
full pace." Brief: BUILD-BRIEF-PHASE2.md (slices 4–7 + spec 0.2).
Built on the Oracle (board re-booked for lane `jacquard-build`,
agent-inbox commit 001dcbd), in the verified clone, checking the
remote after every push — the Phase 1 lesson about unverified
agent reports is applied by construction this phase: all code
below was written in the coordinator's own verified environment,
and every slice verdict cites a cold-clone test run.

**Additional resources (Casey, 2026-11-02), and how they are
used.** (1) DeepInfra hosted models for iterative development
(critique passes, fixture generation) — used for slice-draft
critique where it helps, logged here when material. (2) Typesafe
Jev decision models: Casey — "decision models might play a role,
play with it." Constitutional constraint, recorded as binding:
decision models are ADVISORS only. A Jev-class reading may be
published as a sense and consumed by policy as data; no allow/deny
path may depend on a model verdict — the record gates. They enter
only behind a provider interface (section 13 of the spec): the
kernel imports no provider-specific code; Typesafe is the first
plugged-in provider and the experiment subject. (3) Cloudflare
Workers AI capacity for build help and play-testing, as it
accelerates.

**Spec 0.2 bump (lands first, so later slices don't churn).**
Version and seal move to jacquard/0.2; golden vectors regenerated;
suite still 46 green. The EXAMPLE refusal name — used by the 0.1
implementation but missing from 0.1's refusal list — is now listed
(the Phase 1 erratum, folded in). The 0.2 folded state declares,
up front, every section Phase 2 needs (machines,
machine_instances, budgets, prices, rules) so slices 5–7 extend
the fold's behaviour without changing the state hash again.
Budget accounting folds from the log: `budget` entries grant,
`price` entries post prices, applied `spend` effects in execution
entries deduct amount × price-at-that-point-in-the-log (default
price 1). Decision entries now also close queue items on
`rejects` and `expires` (the approval lifecycle needs both; 0.1
only had `releases`).

**Machine profile decisions (slice 4).** The repo's own text
format and checker, as the brief directs (the .NET StateSmith CLI
is NOT integrated this phase: it would put a .NET toolchain in the
definition path of a Python reference kernel whose spec must stay
language-neutral, and the profile is deliberately smaller than
StateSmith's — flat, total, dictionary-named actions only. The
choice and this reason are recorded here per the brief.)
Format: one directive per line — `machine`, `initial:`,
`terminal:` (a list, or `none`), `events:`, transitions
`from -> to : event [guard-word] [/ action-word]`, an optional
`otherwise` fallback per (state, event), and `ignore event in
s1, s2` / `ignore event in *` (every state with no transition for
that event). Totality is checked against the DECLARED event
alphabet: every (state, event) pair must transition or be
explicitly ignored. DEAD means: a non-terminal state with no
outgoing transitions, or (when terminals are declared) a state
that cannot reach any terminal. AMBIGUOUS means: two guarded
transitions on one (state, event), or more than one unguarded
non-fallback transition, or a plain transition competing with an
`otherwise` fallback — guards cannot be proven disjoint
statically, so the profile allows at most one guarded transition
plus one `otherwise` per (state, event). Guard words must have
signature (map -> bool); action words take the event payload map
and are evaluated for the requests they emit. Every step writes a
`transition` entry; instance state is a fold of those entries.

## 2026-11-02 — Slice 4: lifecycle machines + profile checker

**Delivered.** `src/jacquard/machines.py` (parser + static
checker + firing-order helper), `src/jacquard/lifecycles.py`
(the seven lifecycle machines as profile-definition text),
sequencer integration (machine envelopes; instance create/step
with a transition entry per step; proposal, action and approval
lifecycles driven through the machines; `reject_queued` /
`expire_queued` closing queue items alongside `release_queued`;
`transition_standing` driving the gate's standing view through
the producer-standing machine). Spec section 10 documents the
profile to reimplementation standard. Tests: 31 new (77 total)
— behaviour specs per machine, one deliberately broken machine
per named refusal (UNREACHABLE, DEAD, AMBIGUOUS, NON_TOTAL, plus
SPEC/FIELD word and signature cases), guard/otherwise/action
runtime, and kernel-path tests asserting the log shows the
transition sequence, not just outcomes.

**Design points worth keeping.** (1) Lifecycle stepping is
active only for machines present in the kernel's registry, so a
bare kernel is byte-for-byte the 0.1 kernel — the Phase 1
acceptance suite is untouched by construction, and installing
the lifecycles is the production posture. (2) Guards are
dictionary words whose computed effects must be empty: purity is
checked from computed effects at definition time, not trusted —
a guard that would emit a write is refused SPEC. (3) A machine's
action words are evaluated for the requests they emit, which are
recorded on the transition entry; the machine never executes
effects itself. (4) One real bug caught by the new tests during
development: the checker was first wired to a wrong guess at the
dictionary's internal resolve shape; the test run failed loudly
and the wiring now matches the dictionary's actual contract.
(5) pyproject gained `pythonpath = ["src"]` for pytest: running
a single test file previously failed collection unless another
test module happened to fix the path first — a latent trap for
CI, fixed at the root.

**Not done in this slice (by design).** The commit-batch and
worker machines are defined, checked and behaviour-tested as
machines, but no kernel path drives them yet — batching belongs
to the executor work and workers to the operator surface
(Phase 3). The standing-rule machine is driven by slice 6.

**Pre-push critique (DeepInfra, DeepSeek-V4.1-Flash-1017).** One
spec-consistency pass over sections 2/7/10 plus the checker
summary, before pushing. It found one real contradiction —
section 10.3's firing-order text implied plain and guarded
transitions could coexist, which 10.2's AMBIGUOUS rule forbids —
plus three under-pinnings (guard firing is now stated as "the
result stack is exactly [true]"; the release path's step origins
(from tentative) are stated; the state hash is pinned to the nine
named sections with their wrapper shapes) and two docstring
drifts in machines.py (SPEC mis-described as covering event
references — those are FIELD; "total by construction" corrected
to "total by check"). All fixed in the consistency-pass commit
below. One critique item was an artifact of the review prompt's
section splicing, not of the spec; noted and dismissed. Cost:
~3.6k tokens, fractions of a cent — the contra-find alone was
worth it.

## 2026-11-02 — Slice 5: WFQ scheduling, budgets/prices, senses, provider seam

**Delivered.** `scheduler.py` — one WFQ implementation for the
three arenas (admission via `Sequencer.submit_batch`, executor
slots, decision-queue attention via `Sequencer.decision_order`):
finish-tag queueing over (producer, class) flows, baseline
weight 1, purchased extra weight decaying with a virtual-time
half-life, aging past a wait threshold. `Sequencer.grant_budget`
/ `post_price` / `buy_weight` over the folded accounts (budget
entries grant, price entries post, applied spends deduct at the
price in force at their log position; default price 1; an
unaffordable purchase is a CONSERVATION refusal — degrade, never
borrow). `senses.py` — compute/publish framework: queue-depth,
output-use:<producer> (records projection as a reading),
starvation (live scheduler counters), calibration-drift
(honestly a stub; its method text says per-rule calibration is
the learner's). Values are canonical types only — rates are
integer basis points, because sense entries live in the log and
the log admits no floats. `providers.py` — the decision-model
seam (spec section 13), plus `adapters/typesafe_jev.py`, the
first adapter, deliberately OUTSIDE the kernel package.
Tests: 24 new (101 total), including the acceptance shapes —
quiet flow served within its first four tags under a 57-item
flood; a weight-4 buyer landing at 36–44 of 50 serves against a
baseline flow (purchased share 40, capture bounded, baseline not
starved); spend accounting replayed from the log alone to the
unit and to the same state hash.

**Jev experiment (advisor measurement, tools/jev_experiment.py).**
11 blind judgements against record-derived ground truth: 6
routine dispatches from the real gpu-queue record, the hold and
halt reconstructed fixtures, 3 policy/1 cases. Agreement 10/11
(91%), latency mean 0.60s / max 0.76s per call. The single
disagreement is the finding: on the hold fixture Jev said DENY
where the rule says HOLD (queue). That distinction is
load-bearing in this design — a hold is a reversible batching
for a human, a deny is terminal — and the model flattened it.
Exactly the failure mode the constitution predicts: a decision
model is a witness with a flattening habit, so its readings are
senses (evidence, labelled, ignorable), never gate inputs. A
constitutional test pins this: decisions are byte-identical with
and without a 99%-confident judgement sense published, and the
kernel's decision-path modules contain no provider imports
(asserted by grep in the test suite).

## 2026-11-02 — Slice 6: the learner

**Delivered.** `learner.py` driving the standing-rule machine
through the full R10 pipeline: mining (shape = producer × class
× exact effect set over the first 70% of primary decisions;
support ≥3, dominance ≥80%), a generated pure recogniser
definition per candidate (computed effects: none), offline
evaluation on the held-out 30%, shadow, canary, active — each
promotion gated on scored agreement (≥90% over ≥3 fresh
samples), production scoring with automatic demotion, and
one-call revocation. The P9 `similar` primitive is implemented
now (shape-key lookup over the actor's own decision history);
the Phase 1 "honestly returns []" stub is gone. Tests: 9 new
(110 total) covering mining on the gpu-queue pattern in
miniature plus a synthetic pattern, shadow non-interference,
the full pipeline to an active rule that verifiably decides
(`decided_by` on the decision entry), promotion refusal without
evidence, and revocation immediacy.

**The constitutional detail that matters.** When a rule
decides, the decision entry also records `policy_outcome` —
what policy/1 would have done. Production scoring compares the
rule against THAT, never against its own decisions; otherwise
"agreement" for an active rule is a tautology and regression is
undetectable. The planted-regression test works exactly this
way: the producer is suspended, policy denies, the hook refuses
to override a suspension (standing is constitutional), the
rule's stored prediction keeps disagreeing with the recorded
policy outcomes, and check_demotions demotes it with the
regress transition and the 0% agreement score in the log.

**Honest limits.** Mining is shape-frequency only — no
sequence patterns beyond repetition of a shape; the recogniser
is exact-match on the effect set, so near-miss shapes are
different shapes. Both are stated in spec section 12's terms
(minimum support, dominance) rather than dressed up.
Quarantine exists in the machine but nothing drives a rule
into it yet — it is the operator's lever, wired when the
operator surface lands (Phase 3, slice 10).

## 2026-11-02 — Slice 7: state export bundles (Phase 2 complete)

**Delivered.** `bundle.py`: export assembles configuration
(committed units), definitions (raw form — name, signature,
body, examples), machine definitions (parsed form), and
standing rules with `stage_at_export` as provenance. Import
validates the format id and key structure, scans the structural
sections for anything that must not travel, and re-enters
everything through the destination's own gates — dictionary
(examples re-run, effects recomputed), profile checker, and
the standing-rule machine at shadow, always shadow, with the
export stage recorded as `imported_from_stage` and nothing
more. Budgets, standing, credentials and authority are absent
by construction, and present-by-tampering is refused
PROVENANCE, as are content collisions; identical re-imports
skip cleanly. Tests: 9 new (119 total) — the two-kernel
round-trip, an imported active-in-A rule verifiably NOT
deciding in B until it re-earns activation on B's own record,
and the three named smuggling attempts (credential section,
budget in config, `stage: active` on a rule) each refused by
name with the destination untouched.

**Phase 2 verdict.** Slices 4–7 and spec 0.2 are in: the
kernel's lifecycles are data (checked machine definitions), its
scarce resources are fairly scheduled and accounted from the
log, its readings are named senses with methods, decision
models testify as advisors behind a provider seam and never
gate, learned rules climb a tested pipeline and fall down it
automatically, and state moves between kernels without moving
trust. Suite: 46 -> 119 tests, all green from cold clones at
every slice. What Phase 2 deliberately did NOT do: no executor
(real effects still stop at the log's applied lists), no
operator surface beyond the Python API, no second-language
implementation yet — Phase 3's slices 8–11, in order.

## 2026-11-02 — Slice 8: second-language conformance (TypeScript, spec-only)

**Result: PASS, with three real divergences found and fixed —
all in the spec, none in either implementation's logic.** The
implementer (an agent given SPEC.md, the vectors, and the
replay fixture only — no Python source) reproduced: the seal,
the vector entry chain, the checkpoint fold, the envelope id,
all 3,295 replay entry hashes, and the replay fold to the
identical state hash 9f434ef1…. Its gap report (kept at
conformance/ts/GAPS.md) lists 15 underdeterminations. Disposition
of each, per the brief's rule (divergence = spec bug first):

- Pinned, reading already matched the reference: key-sort
  collation (#1, code-point order), integer conformance range
  (#2, safe range, refuse-don't-approximate), seal = raw string
  bytes (#4), envelope validation enumerated in full (#5),
  entry-hash input and the vectors' record shape (#6), budget
  key creation (#14), unknown kinds — writer refuses, folder
  ignores (#15), budget/price body schemas (#10).
- Root fix for #13: new spec section 2.1 pins every entry
  kind's body schema and folded representation.
- Three REAL divergences, latent because the fixtures held only
  4 of 12 entry kinds: machine_instances folded value (#9 —
  implementer read a bare state string; the reference folds
  {"machine", "state"}), the rules folded value (#11 — whole
  body vs body.rule), and the import entry (#12 — implementer
  applied units from the body; the reference gives import
  entries no fold effect). All three pinned to the reference's
  behaviour in 2.1, the TS fold corrected to the pinned text,
  and a new fixture (conformance/full-log.json.gz, 25 entries,
  all 11 emitted kinds) now discriminates them: checker item g.
- The escaping round (#3) deserves its own sentence: the
  implementer read raw UTF-8; the coordinator's first spec
  amendment pinned the ASCII-escaped form FROM MEMORY of what
  the reference "must" do — and the new non-ASCII golden vector
  (a café-☃ checkpoint, added to gen_vectors.py for exactly
  this) refuted the amendment: the reference emits raw UTF-8.
  The spec now pins raw UTF-8, and section 1 records that the
  vector, not memory, settled it. This is the anchored-iteration
  doctrine working as intended, on the coordinator.

**The /tmp incident (recorded, owned).** Mid-slice the
development VM's /tmp was reset; the coordinator's local
working clone — including the not-yet-pushed Phase 3 opening
commit and the replay fixture — vanished. Nothing already
pushed was at risk (GitHub + the Oracle checkout held
everything through Phase 2). Recovery: the fixture regenerated
bit-identically (the replay is deterministic; the state hash
matched to the digit), and the TS work survived in the
implementer's own backup. Lesson applied immediately: the
working clone now lives under ~/workspace, not /tmp, and
commits push per slice without exception.

**Scoped honestly:** the vectors' definitions and final-state
sections encode dictionary evaluation and sequencer execution;
the fold-scope checker reports them SKIP rather than faking
coverage. They remain pinned for a full second implementation
(the Rust port is the expected candidate, Casey's call).

## 2026-11-02 — Slice 9: executor + live shadow trial

**Executor (delivered first).** `adapters/executor.py` — a
deployment adapter outside the kernel, like the provider
adapters: consumes action instances standing at `dispatched`,
runs payload commands ({"cmd": [...], "compensate": [...]
optional}) under bubblewrap (read-only root, private /tmp, no
network) or a scrubbed subprocess fallback, journals every run
BEFORE reporting the outcome through the action machine, and
treats the action id as the idempotency key (a duplicate
delivery re-reports the recorded outcome, never re-runs).
Battery tests: confirm, fail->compensate, duplicate delivery
with the side effect happening exactly once, bad payload ->
failed without running; the bwrap isolation test runs where
bubblewrap exists (the Oracle; it skips on machines without
it). One kernel change rides along: action indices now count
a proposal's dispatch requests only (spec 10.4 says
"action-<index>"; the index is now unambiguous), so an executor
can resolve action-<n> to the n-th dispatch in the execution
entry. Spec section 10.5 (below) states the executor contract.

**Shadow trial — window and count, stated BEFORE running.**
Stream: the agent-inbox booking board (schedule/*.md in
~/agent-inbox on the Oracle), full git history 2026-10-27 to
2026-11-02, 63 commits touching schedule/. Every row's first
appearance is one proposal item; the incumbent outcome for
every item is "accepted" (the board took them all — that is
what makes disagreements interesting rather than the reverse).
Shadow rule: policy/1 via a real shadow Sequencer, plus a
harness-computed contention flag (exclusive-seat overlap with
an active booking) that would queue the item. The flag is
harness-side for a stated reason: interval overlap over a list
of booking maps is not expressible in the dictionary with the
current 26 primitives (no iteration over lists) — a genuine
primitive-gap finding this trial exists to surface, recorded
here rather than engineered around.

**Shadow trial — result.** 68 proposal items from the board's
history; 52 decidable (6 retroactive notes, 10 unparseable);
agreement 46/52 = 88%; 6 disagreements, each classified in
docs/shadow-trial-2026-11-02.md: 3 policy gap (conditional
starts, a Casey-directed priority override — expressiveness
the board and policy/1 both lack), 3 incumbent wrong (real
double-bookings of exclusive seats, one costing a re-plan),
0 Jacquard wrong in the final run. The first run flagged 20:
auditing them exposed two harness defects (stale bookings
contending; table-edit re-commits counted as new proposals),
both fixed and re-run, and the 14 phantom disagreements are
recorded in the report as Jacquard-wrong (harness), not
silently replaced. Headline finding (F1): interval contention
over committed state is inexpressible with the 26 primitives
(no list iteration) — the trial's most valuable output, and a
spec-revision question for Casey, not something fixed quietly
here.

## Slice 10 — operator CLI + cold-agent drill (2026-11-02)

`tools/jq.py`: the decision queue as an operator surface over a
persistent kernel log. Commands: seed-demo, queue, decide
(approve/deny, single or --batch), execute (drives the slice 9
executor), replay, status. Approvals are HASH-BOUND: the binding
is the hash of the decision entry that queued the item; a
mismatch fails and changes nothing. Batch files take
`<id> <binding>` lines (decided with the command's action) or
mixed `<approve|deny> <id> <binding>` lines; a batch processes
every line and exits 1 if any item failed.

Acceptance: tests/test_cli.py drives the CLI as a subprocess —
the full drill (seed → queue → wrong-hash refusal → batch
decisions → queue empty → execute → action confirmed → replay
matching the log), seed-demo's refusal of a non-empty log, and
mixed batches. 4 passed.

**Cold-agent drill.** A fresh agent was given ONLY the repo and
the README's quickstart and asked to reach the success state.
Verdict: DRILL PASSED — every README success marker reached on a
fresh log, no failed step. It found six README/CLI defects; all
fixed in this slice before landing, per the brief's rule that
drill failures are repo bugs: (1) seed-demo on an existing log
crashed with a raw traceback AND partially mutated the log —
now it refuses cleanly ("fresh log" message, exit 1, log
byte-identical) and the README states the fresh-log
precondition; (2) step 3 now says either approve/deny assignment
works, with the canonical one named; (3) step 5 now says replay
runs once per id and includes the dispatched proposal; (4)
step 4/5 phrasing now matches the CLI's actual output lines;
(5) the README status line still claimed the operator CLI was
"not built yet" — corrected; (6) batch mode now supports mixed
approve/deny lines, as documented.

## Slice 11 — release hardening (2026-11-02)

CI (.github/workflows/ci.yml): pytest suite + TypeScript
conformance on every push and pull request (Python 3.12,
Node 22, ubuntu-latest). Package version aligned with the
spec: pyproject 0.1.0 → 0.2.0. CHANGELOG.md added, derived
from this log (0.1.0 = Phase 1; 0.2.0 = Phases 2–3). README
brought to release state: Phases 2 and 3 marked complete, the
"not built yet" line now names only what is genuinely absent
(a network service; distribution beyond the repo).

Release: tag v0.2.0. Acceptance is verified from the TAG
artifact — a fresh clone checked out at the tag, suite and
operator drill re-run there — not from the working tree that
built it.

## Phase 4 — completeness probes, opening (2026-11-02)

**Authorisation.** Casey, 2026-11-02 12:07 AKST, ruling on the
Phase 3 report's open questions: the F1/F2 items (interval
contention, conditional starts, authority priority) "sound like
first-class concepts"; figure them out "with simulations and on
the actual test side"; the system is not complete yet and
something may need adding to the primitives — "but of course we
don't want to add any more than we need to so think closely."
Charter: ~/workspace/cybernetic-architecture/BUILD-BRIEF-PHASE4.md.
Board: agent-inbox 5816fa4 (oracle box, lane jacquard-build).

**Discipline.** An escalation ladder, cheapest first — policy
content, data, machine, sense, and only then ONE new pure form,
general or not at all. A bespoke primitive per gap is a failure
of this phase, not a result. Simulations and adversarial tests on
the real booking-board history decide the rungs; the findings doc
(docs/completeness-probes-2026-11-02.md) is written BEFORE any
implementation, and only the winning minimal set is then built as
a real slice.

**Coordinator recon (before any probe code).** The kernel facts
the probes turn on, verified against the source at 3ce55ff:

- Words cannot recurse (references must resolve to previously
  defined words) and cannot iterate: the only list consumers are
  count/sum/min/max/contains/first; there is no tail/rest/index
  form, and no way to project a field across a list of maps. So
  the rung-1 question for Probe A is not "is it awkward" but "can
  a word even address the second element of a committed list" —
  the probe will prove the wall with concrete counterexamples
  rather than assert it.
- The decision path (policy/1 + the learner rule hook) is
  content-blind: it sees producer, class and effects, never the
  proposal body. Any content-dependent gate must therefore live
  in a machine guard, a sense, or new sequencer wiring — the
  probes test which.
- Senses already take parameterised subjects
  (compute_sense partitions name at the first colon), publish as
  log entries with {value, method, as_of_seq}, and are consumed
  by words via the sense primitive. A parameterised contention
  sense is a rung-4 candidate that needs no evaluator change.
- But: a guard word cannot build a parameterised sense name from
  integer fields (cat is string-only; there is no int->str
  primitive). The sense NAME is an address; the probe driver
  constructs it from the validated candidate fields, and the
  findings will state that production wiring must construct it
  inside the sequencer at decision time, from the same body —
  a proposer-supplied address would be a trust hole.
- decision_queue folds the whole decision body, so a wait spec
  carried on a queued decision survives replay with NO new fold
  section (the nine sections stay nine). release_queued /
  expire_queued already execute/expire queued proposals: a
  "pump" that evaluates wait guards on each commit is wiring,
  not new evaluation power.
- Authority provenance has a trap: policy/1 lets any producer
  write any unit, so a rank grant stored as a plain unit can be
  self-granted. The Probe C candidate therefore reads grants
  through an authority SENSE whose method counts only
  operator-authored grant writes found in execution entries
  (entries carry their producer). The self-grant attack is a
  mandatory probe scenario, not an afterthought.

**Probe team.** Three workstreams: (1) corpus + Probe A
(rung-1 attempts, contention sense candidate, fold-form
candidate measured against it); (2) Probe B (wait-condition
prototype + the brief's five scenarios); (3) an INDEPENDENT
author for Probe A's adversarial synthetic corpus — different
agent from the candidate implementer, labels derived from the
shadow trial's stated rules only, ambiguities flagged rather
than guessed. Probe C follows once the Probe A sense interface
exists (it reuses it).

## Phase 4 — completeness probes: results (2026-11-02)

Full findings: docs/completeness-probes-2026-11-02.md. The
probes live in tests/probes/ (harness + corpora; candidate code
quarantined there until the slice promotes it).

**Probe A (contention, F1).** Rung 1 proven impossible with
three exhibits (no list form yields a second element; a
first-only word silently answers wrong; sum over maps refuses
FIELD and count cannot distinguish equal-count states of
opposite label). Rung 4 — a parameterised `contention` sense
consumed by machine guards — reproduces all 52 shadow
decisions on the real board corpus, contender id sets
included, and scores 35/35 on the independent adversarial
corpus after the probe's own correction: the first subject
grammar omitted the candidate id (33/35), the id became the
sixth subject field, and a gate-by-gate check confirms those
six are exactly the candidate fields the reference predicate
reads. Corpus pinned to the trial's window (first 63
schedule commits, head 0d23fd56) because the live board grew
past the snapshot during this phase. Cost: 1.02 ms median per
reading at 1,000 bookings/box. Staleness pinned by test: the
reading must be published inside the decision step.
**Rung 5 (fold form) built and rejected on evidence:** agrees
everywhere the sense does, but ~56x the evaluation cost, a
whole-list rewrite tax per commit (130,891 B write value at
1,000 bookings vs a constant 128 B), and a demonstrated
computed-effects hole — a Tier-E verb hidden in the quotation
computes as effect-free under the stock token walk. The walk
fix is known; it is a spec programme, not a patch, and buys
nothing the sense lacks on this evidence.

**Probe B (conditional starts, F2a).** Rung 2: a `wait` field
on the proposal body ({guard, deadline_seq}); the guard is an
ordinary pure word; the waiter sits in the decision queue —
the fold copies whole decision bodies, so the nine fold
sections stay nine. 13/13 scenarios pass, including the
rung-1 contrast (the incumbent submit-when-it-fires pattern
executes fine and leaves a log that can answer neither "what
are we waiting for?" nor "why did this start?"). Semantics
pinned state-based, not edge-based: land-then-retract before
re-evaluation does not start the waiter; deadline is an
absolute log position, queueing's own 5 entries included.
Composition rule for the slice, from the probe's open
interaction: a fired guard sends the proposal through the
ordinary policy decision fresh — guard release never bypasses
the gate.

**Probe C (authority priority, F2b).** Decomposition held:
rank is rung-2 data (records store effective rank =
min(asserted, ceiling) plus asserted_rank); recognition is a
rung-4 `authority` sense counting only operator-authored
grant writes — the mandatory self-grant attack lands its unit
(authority/mallory = 99 in committed state) and changes
nothing, because provenance comes from execution entries, not
from the value. Override is rung-3: preemption as ordinary
operator proposals + a PREEMPTED machine transition +
preemption records; audit replay from the log alone returns
{winner, winner_producer, rank, grant_seq} with ordering
proven. 8/8 scenarios. The probe caught a contradiction in
the coordinator's staged brief (binary vs ceiling rank);
the ceiling won and is recorded in the findings. One
deliberate deviation from the charter's letter, reasoned in
the findings: a rank tie is queued under a named `tie`
transition, not refused — a tie between legitimate
authorities is a batched-decision item under Casey's
standing ruling, and "no silent winner" is fully satisfied.

**Suite:** 128 -> 163 with the probes, nothing weakened, no
src/ file touched yet. Next: DeepInfra critique of the
findings, then the implementation slice (spec 0.3) for the
minimal set the findings name.

**Critique pass (2026-11-02).** The findings draft went to a
DeepInfra critic (DeepSeek-V4.1-Flash; prompt = design
context + ladder + the full draft; ~4k completion tokens,
cost ~$0.002) before implementation, per the phase brief.
Blows that landed and changed the findings + slice set: the
wait composition was under-specified — the ordering rules
(post-fold evaluation, guard-true beats deadline at equal
seq, fixpoint pump scope, refusing-guard disposition,
decision supersession) are now pinned in the findings;
Probe C(ii) was rewritten from "rung 2 is attackable" to the
structural argument (the gate is target-blind: effects carry
no unit, so no policy version can gate writes by target);
the authority method gained its three filters and last-wins
ceiling resolution; the tie's interim disposition
(incumbent holds while the challenger waits) is stated
instead of hiding inside "no silent winner"; unclassified
seat strings now fail closed through the guard instead of
clearing silently. Not adopted, reasons recorded in the
findings: trimming definition-words (free currency) and
profile-defined senses (no spec'd registration mechanism
exists). The findings doc in this commit is the
post-critique version; the pre-critique draft is in git
history at de1813a.

## Phase 4 — implementation slice (spec 0.3), in progress (2026-11-02)

Steps 1–4 of the slice brief are built and committed locally
(not yet pushed; §5 spec/vectors/conformance and the §6
close-out wait on the Probe B ruling below):

- **Senses (1a9a2f4).** `contention` and `authority` promoted
  from tests/probes into src/jacquard/senses.py. Contention
  gains the findings' `unclassified` list (candidate's seat +
  seats of status-"active" rows under the prefix, in neither
  the exclusive set nor {"detached"}); the method string states
  it. Authority's method states its three filters and last-wins.
- **Wait + pump (2523e88).** As briefed: pre-append guard
  validation/evaluation, queueing with the wait spec on the
  decision entry and no approval instance, the fixpoint pump at
  the eight pinned exits, fresh policy decision on a fired
  guard, guard-true beats deadline, refusing guards recorded
  once per state change, reason parameters on
  release/reject/expire_queued. Two deviations, both recorded:
  (1) the underdeclared check is also made pre-append for
  wait-carrying proposals (the probe's stated simplification —
  a queued waiter never reaches the normal path's check, and
  queueing an underdeclared proposal would be worse); the
  refusal appends nothing, unlike the normal path's fault
  decision. (2) Probe B's S3b (land, retract, then pump) is
  staged in production as land+retract inside ONE commit batch,
  because the production pump runs inside the landing
  submission itself — the findings' blind-interval residual,
  not a semantics change.
- **Booking profile (b3bd37a) + CLI (da56b3b).** booking.py as
  briefed (booking-clear requires count == 0 AND unclassified
  empty; dispose rejects with reason preempted-by:<winner-id>);
  jq queue annotates waiting items and authority ties.
  Production tests re-register the production senses in a
  fixture (probe modules overwrite SENSES at runtime — the
  brief's registry hazard, real in full-suite runs).
- **Suite: 197 passed, 7 failed — all 7 in tests/probes/
  test_probe_b.py, and the failure is structural, not a bug
  found in either implementation.** Probe B modelled the pump
  as a harness function (`wait_flow.pump`) called explicitly
  after submissions. The production pump runs INSIDE
  `Sequencer.submit` / `checkpoint` exits, exactly as the slice
  brief pins — so when a probe scenario lands X via
  `seq.submit`, the waiter is already released and executed
  before the probe's own `pump(seq)` runs, and the probe's
  assertion on its pump's action list (`[("released", pid)]`)
  sees `[]`. The outcome the probe asserts everywhere else
  (execution, queue state, audit chain) is the production
  outcome; what is pre-empted is only the probe harness's
  manual trigger. Any sequencer that pumps on submission —
  the briefed design — breaks these 7 assertions; no pump
  placement satisfies both the brief's exit list and the
  probe's manual pump. STOPPED here per the slice's standing
  rule (a production change breaking a probe test is a finding
  to report, not a probe to edit) and reported to the
  coordinator for a ruling: options include (a) accept the 7 as
  superseded by tests/test_wait.py, which ports the same
  scenarios to the production surface, and annotate the probe
  module accordingly; (b) narrow the pump's trigger set —
  contradicts the brief's pinned exits; (c) distinguish
  probe-queued waiters by their approval instance (production
  waiters have none) — a spec-indefensible special case,
  recommended against. Recommendation: (a).

## Phase 4 -- implementation slice: Probe B ruling (2026-11-02)

**Ruling (coordinator).** Option (a), as the stopped builder
recommended. Probe B's harness modelled the pump as a manual
harness function (`wait_flow.pump`) called explicitly after
submissions; production internalised the pump into Sequencer
exits, exactly as the findings pinned (the pump runs before
any public sequencer method that appended entries returns).
The 7 failing tests assert the PROTOTYPE driver's action
lists, which production legitimately pre-empts: when a probe
scenario lands X via `seq.submit`, the waiter is already
released and executed before the probe's own `pump(seq)` runs,
so its asserted action list reads empty. Every scenario's
outcome assertions (execution, queue state, audit chain) are
preserved and strengthened in tests/test_wait.py (23 tests)
against the production surface.

**Disposition (executed verbatim-scoped).** In
tests/probes/test_probe_b.py: a module-docstring note records
the supersession, and exactly the 7 failing action-list tests
carry `pytest.mark.skip` with a reason string naming the
supersession. No assertion was changed, no currently-passing
test was skipped, wait_flow.py's code is untouched (one
docstring note marks it the superseded prototype), and Probe
A/C files are untouched. This mirrors the repo's declared-SKIP
convention from TypeScript conformance: declared, reasoned,
visible. Result: test_probe_b.py reports 6 passed, 7 skipped;
the full suite's only failures are gone without weakening any
check -- the probe remains in the tree as the experiment
record, skips and all.

## Phase 4 -- implementation slice: close (2026-11-02)

Steps 5 and 6 of the slice brief, completing the slice the
stopped builder left at steps 1-4 plus the Probe B ruling.

- **Spec 0.3 (20e55b4).** Version and seal moved everywhere
  the version is named (title, entry `spec` field, seal string
  `jacquard-spec/0.3`; canonical.py SPEC_VERSION / SPEC_SEAL
  aligned). §11.3 gains the contention and authority senses
  in full -- subject grammars, read sets, filters, value shapes
  including `unclassified`, the three-filter + last-wins
  authority method, and the published-value determinism note
  split into its two true halves (refold reproduces state;
  recomputation at as_of_seq reproduces the reading). §7.1 is
  new: the `wait` field -- shape, pre-append validation
  (including the underdeclared pre-check the previous builder
  added, recorded at 2523e88), submission-time evaluation,
  queueing with no approval instance, the pump and its ordering
  rules (post-fold evaluation, guard-true beats deadline,
  fixpoint to 64 passes, refusing guards recorded as
  `wait-guard-refused` and treated not-true, supersession via
  `releases`, deadline an absolute log position including
  queueing's own entries, composition -- a fired guard
  re-decides through policy fresh, never bypasses it). §11.4
  is the booking application profile: record schema with rank
  + asserted_rank, grants with the authority sense as the only
  sanctioned reading, preemption records, tie semantics with
  the incumbent-holds interim disposition, seat classification
  with unclassified fail-closed in the guard. §2.1 lists the
  `wait` / `wait_refusal_at` decision fields; §3 points at
  §7.1 from the proposal body; §9 describes the senses
  vectors. Placements: the wait text sits at §7.1 (it is the
  policy gate it composes with) with the §3 pointer, and the
  profile sits at §11.4, the section booking.py's docstring
  already cited.
- **Vectors.** tools/gen_vectors.py gains a "senses" section
  built from stated entry lists folded by the tool: contention
  clear / two-contender / unclassified-seat cases, authority
  ungranted (a self-grant write, inert under the producer
  filter) / granted-then-regranted (last-wins, ceiling 5 -> 2)
  cases, each {"entries", "subject", "expect":
  {"value", "method", "as_of_seq"}} grouped by sense.
  tests/test_vectors.py verifies the section via fold +
  compute_sense and pins the named expectations in words.
- **Conformance (143c92c).** Fixtures regenerated under 0.3:
  conformance/gen_full_log.py rerun (25 entries, all 11
  emitted kinds). The replay log needed a note: contrary to
  the slice brief's premise, tools/replay_gpu_queue.py has no
  fixture writer -- run_replay() returns a summary and keeps
  its Sequencer internal. Regeneration therefore drove that
  exact code path with a capturing Sequencer subclass and
  wrote the replay's own log in the fixture's established
  shape: 3,295 entries, 1,637 dispatches matching the recorded
  order, chain verified, fold hash recorded. TS checker:
  version constants in conformance/ts/jacquard.ts aligned to
  0.3 (no fold logic changed; the header now says so), sense
  computation declared SKIP in the checker output
  (`vectors.senses`), and GAPS.md gains entry #16 (readings
  are published values computed by kernels, not folded).
  Checker result: 7 PASS (a-g), 3 SKIP (definitions, state,
  senses), exit 0.
- **Probe B disposition (55739d5)** executed as ruled; see the
  ruling entry above. Suite before this close-out's steps:
  197 passed, 7 failed (all probe-B action lists). After:
  198 passed, 7 skipped -- the 7 failures became the 7
  declared skips, and the +1 pass is the new senses-vector
  test. Nothing else moved.
- **Known residual -- two refusing waiters (not fixed).** The
  pump's refusal re-recording skip keys on the waiter's own
  refusal record still being the LAST log entry. One refusing
  waiter: bounded to one record per state change, as specced.
  Two waiters whose guards both refuse defeat the key: each
  pass appends both records alternately (neither record is
  last when its waiter's turn comes), so every pass "changes"
  something and the pump runs to its 64-pass cap -- bounded
  re-recording (at most 64 passes x the refusing waiters'
  records per triggering call), then it stops. Neither waiter
  is lost or crashed into an unrelated submission; both stay
  queued and are re-evaluated on the next commit. The fix (a
  per-waiter last-recorded-position check instead of a
  head-entry check) is a later spec sentence; recorded here as
  a known residual, per instruction, and not fixed in this
  slice.
- **Release.** pyproject 0.3.0; CHANGELOG 0.3.0 derived from
  this log; README status brought current (Phase 4 complete,
  spec 0.3; the "not built yet" line still names only the
  network service and distribution beyond the repo). Tag
  v0.3.0 follows push; cold-clone and tag verification are
  recorded in the addendum entry after this one.

## Phase 4 -- verification addendum (2026-11-02)

Recorded after the push, as the close entry promised.

- **Push.** Local main (the previous builder's five commits
  1a9a2f4..eeab18e plus this finisher's 55739d5, 20e55b4,
  143c92c, 5085899) pushed to origin: adb245e..5085899.
  ls-remote confirms origin/main at 5085899.
- **Cold clone of the pushed main.** Fresh clone from GitHub
  into a clean directory: suite 198 passed, 7 skipped (the
  declared Probe B skips, visible with -rs); TypeScript
  checker 7 PASS (a-g), 3 SKIP (vectors.definitions,
  vectors.state, vectors.senses), exit 0.
- **Tag.** v0.3.0 is tagged on the main that carries this
  addendum; acceptance is verified from the tag artifact (a
  fresh clone checked out at the tag, suite + checker +
  operator drill re-run there), not from the working tree
  that built it -- the Phase 3 discipline.

## Phase 4 — coordinator close-out (2026-11-02)

- **Findings addendum.** The completeness findings gained an
  addendum written for Phase 5 (chartered separately): the
  per-gap rung verdicts restated in adapter terms — what a live
  adapter may rely on (envelope verdicts, the hash-bound batched
  queue, machine transitions as the audit trail, published sense
  readings, the section-13 advisor seam) and what it may not
  (there is no network service yet; booking is the only shipped
  application profile).
- **Programme documents mirrored.** docs/PROGRAMME.md and
  docs/USE-CASE-VOID-SCAN.md are verbatim copies of the
  programme-level documents whose working home is the programme
  workspace; they are mirrored here so the public record sits
  alongside the build it describes. Both describe Phase 4 as in
  flight because that was true when they were written; Phase 4
  has since landed (this log, spec 0.3, tag v0.3.0). The copies
  are snapshots and were not edited to match — the drift is
  recorded here and in the coordinator's report rather than
  silently corrected.

## Phase 5 — beachhead 1 build-out (opened 2026-11-02)

Charter: BUILD-BRIEF-PHASE5.md (Casey, "Great, go", on the void
scan). Four slices: 12 a live adapter to one real coding agent,
13 the network service, 14 batched queue notifications, 15 the
measured proof run. The Phase 4 findings addendum is the design
input: the adapter builds against the envelope verdict
vocabulary, the hash-bound batched queue, machine transitions
as the audit trail, and published sense readings; it authors
its own profile definitions against the profile checker
(booking is the only shipped profile).

- **Host surface chosen for slice 12: ZCode** (3.16.3, on the
  Oracle, authenticated on the already-paid plan). Its hook
  system offers exactly the callout the brief wants:
  `PreToolUse` / `PermissionRequest` events from a workspace
  `.zcode/config.json` (`hooks.enabled: true`), a strict-JSON
  verdict (`allow` / `ask` / `deny`), exit code 2 = deny. The
  adapter is workspace-scoped configuration plus a hook process:
  removing the config restores the host exactly. Claude Code
  hooks were the briefs named candidate

## Phase 5 — beachhead 1 build-out (opened 2026-11-02)

Charter: BUILD-BRIEF-PHASE5.md (Casey, "Great, go", on the void
scan). Four slices: 12 a live adapter to one real coding agent,
13 the network service, 14 batched queue notifications, 15 the
measured proof run. The Phase 4 findings addendum is the design
input: the adapter builds against the envelope verdict
vocabulary, the hash-bound batched queue, machine transitions
as the audit trail, and published sense readings; it authors
its own profile definitions against the profile checker
(booking is the only shipped profile).

- **Host surface chosen for slice 12: ZCode** (3.16.3, on the
  Oracle, authenticated on the already-paid plan). Its hook
  system offers exactly the callout the brief wants:
  `PreToolUse` / `PermissionRequest` events from a workspace
  `.zcode/config.json` (`hooks.enabled: true`), a strict-JSON
  verdict (`allow` / `ask` / `deny`), exit code 2 = deny. The
  adapter is workspace-scoped configuration plus a hook process:
  removing the config restores the host exactly. Claude Code
  hooks were the brief's named candidate; Claude Code is not
  installed or authenticated on the build box, and ZCode is the
  fleet seat that is — time-to-integrate is a competitive
  variable (scan hardening), so the live surface wins.
- **The V2 contrast, stated before building:** ZCode hooks run
  inline, so a queued item blocks THAT action in the host. The
  adapter returns deny-with-reason naming the queue id and the
  binding hash; the agent is free to do other work and retry
  after the batch is decided, and an approval can compile into
  a governed standing rule so the retry — and every later twin
  — fast-paths. Permit blocks the producer until timeout =
  reject; here nothing times out into a rejection, and the
  queue is decided in one operator pass. Where the host forces
  a synchronous shape anyway, the report will say so plainly.
- **Rank-tie disposition** (interim, Phase 4): challenger
  queues, incumbent holds. Nothing in Phase 5 depends on
  flipping it.
- Slice 15 window and workload will be stated here before the
  proof run starts, per the brief.
