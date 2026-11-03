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

## Phase 5 — slice 13: the network service (2026-11-02)

The README's last "not built yet" item, built. A second machine
can now operate the kernel over HTTP with the CLI's verbs and
the CLI's hash-binding rules.

- **One rendering path.** The queue listing, replay, status
  text, the one-line decision outcomes, the binding hash and
  the demo seed moved out of tools/jq.py into
  src/jacquard/present.py; jq.py now prints what present.py
  renders, and the service returns the same strings. Byte-for-
  byte agreement between CLI and service is therefore by
  construction — and still proven by test (below), because a
  construction claim is testimony until a diff runs. The CLI's
  own suite (tests/test_cli.py, incl. the slice-10 drill,
  waiting-item annotation and mixed batches) passes unchanged
  against the refactor.
- **The service** (src/jacquard/service.py, stdlib
  http.server only — zero-dependency is a property, kept;
  runner tools/jqserve.py): POST /seed-demo, POST /proposals
  (one envelope in, the kernel's verdict out), GET /senses and
  GET /senses/<name>, GET /queue, POST /decide (single, and
  batch via `decisions` or `batch` — a stale hash fails that
  item with the CLI's binding-mismatch line and changes
  nothing; the rest of a batch still processes, as the CLI
  does), GET /replay/<proposal_id>, GET /status. Every request
  opens the log fresh from disk, so the service acts on the
  current record even when the CLI appended between requests;
  mutations are serialised under a lock. Text-bearing
  responses carry the exact CLI rendering in a `text` field
  alongside structured data (`items`, `status`, `results`).
- **Senses are publications, not computations.** Per the
  Phase 4 findings addendum — contention readings are computed
  by the kernel that owns the record; a remote adapter
  consumes published readings and never recomputes — the
  senses endpoints serve only what the owning kernel has
  published into its log (folded state), 404 for an
  unpublished name. A test pins the semantics: after a
  decision moves the queue, the published queue-depth reading
  still reports its as_of value until the kernel republishes.
- **Posture.** Binds 127.0.0.1:8730 by default. A non-loopback
  bind requires BOTH --allow-remote AND a bearer token
  (JACQUARD_SERVICE_TOKEN env); without the token the service
  refuses to start off loopback (tested at the serve() seam).
  With a token set, every request is checked (hmac
  compare_digest); missing/wrong token → 401 and no state
  change (tested: log bytes identical after rejected reads
  and writes). No TLS, and the README's service section says
  what that means plainly: the token is a door lock against
  unauthorised LAN machines, not encryption, not per-user
  identity; run it on a trusted LAN or in a tunnel.
- **Tests** (tests/test_service.py, 8 tests): every verb over
  HTTP against a seeded log; the drill-equivalence test —
  seed/queue/decide/replay through HTTP vs the CLI on two
  identically seeded logs, queue/status/replay texts diffed
  byte-for-byte at each step and the two log files asserted
  byte-identical after the decisions; batch decide; stale-hash
  decide over HTTP (409, log bytes unchanged, item still
  queued); seed on a non-empty log refused over HTTP; bind
  posture; token checks. Suite: 206 passed, 7 skipped (the
  declared Probe B skips) — was 198 + 7 before this slice.
- **Not in this slice:** execute stays CLI-side (the sandboxed
  executor runs where the log lives; the brief's drill surface
  for the service is seed/queue/decide/replay), and the
  cross-machine acceptance — the drill re-run through the
  service from a second machine — is the coordinator's run
  after this lands. Exact run line, on the Oracle's loopback:
  `python3 tools/jqserve.py --log <kernel.jsonl>` (default
  127.0.0.1:8730). Nothing here depends on the interim
  rank-tie disposition.

- **Slice 13 coordinator verification (cross-machine).** The
  builder's same-host evidence was re-checked from a second
  machine (the coordinator's VM) over an SSH tunnel to the
  Oracle's loopback 8730: seed and status answered; the queue
  was read remotely; one item was APPROVED remotely with its
  binding hash (the decide executed downstream — the replay
  shows the execution and the close); and the service's queue
  and replay texts were diffed against the CLI's on the same
  log — byte-identical both times. Slice 13 acceptance met:
  the slice-10 drill verbs run end-to-end through the service
  from another machine, and CLI and service agree exactly.

## Phase 5 — slice 14: batched queue notifications (2026-11-02)
Built `tools/jqnotify.py` + `tests/test_jqnotify.py` (15 tests) in
a parallel clone (~/jacquard-s14) while slices 12/13 land in the
main clone; merged by rebase per the coordination protocol.
**What it does.** Folds the kernel log, computes the current
decision-queue snapshot, and fires ONE batched summary when the
queue is at or beyond a configurable age or count. The summary
is exactly the brief's shape: counts by effect class (per-effect
counts plus per-class counts), the oldest item's age, total
queue depth, and the queue snapshot hash. No per-item listing
by default; `--verbose` lists ids on the console only. The
notification proposes nothing and approves nothing; decisions
stay in the CLI/service. Thresholds come from CLI flags
(`--max-age-s` / `--max-count`) or the environment
(JQNOTIFY_MAX_AGE_S / JQNOTIFY_MAX_COUNT); defaults 100 / 5.
**Age is log time, and the brief's word "timestamp" needed a
ruling.** The kernel log carries no wall-clock timestamps at
all — its clock is the log itself (spec section 5: P2 `now` is
the entry count, P6 `age` is staleness in entries). So an item's
age is defined as (latest substantive seq) minus (seq of the
decision entry that queued it), where "substantive" excludes
this tool's own notification records, so a notification never
ages the queue it reports on. Every summary number is a pure
function of the log prefix and re-derivable by re-folding; the
summary states its age mode (`log-entries`) in every emission.
There is deliberately no wall-clock mode: there is no
wall-clock data in the log to verify one against. The flag
spelling `--max-age-s` from the brief is kept (alias
`--max-age`); its unit is log entries, stated in --help, the
module docstring, and the README.
**The log record is a checkpoint, and why not a new kind.** The
firing appends a `checkpoint` entry (body name
`queue-notification`) carrying the snapshot hash, the exact
summary numbers, the tripped thresholds, and the pre-append
folded state hash. A new entry kind was rejected: the kind list
is closed in spec section 2 (twelve kinds), `Log.append`
enforces it, and the TypeScript conformance checker folds
fixtures by kind — a thirteenth kind is a spec change, not a
notification. `checkpoint` is the existing kind whose fold is
defined as no fold effect (spec section 2.1; state.py has no
checkpoint branch), so the record preserves fold determinism
and the nine-section state shape exactly — a test pins that the
state hash after the append equals the state hash before it.
Flagged openly: the body carries annotation fields beyond the
minimal checkpoint shape {"name", "state_hash"}; that is a
payload on a fold-transparent kind, not a fold change.
Verification is a mode, not a promise: `--verify` re-folds the
prefix before every notification record in a log and recomputes
its summary.
**Repeat suppression.** A state file (default
`<log>.jqnotify-state.json`) records the last notified snapshot
hash, oldest item + age, and latest substantive seq. Re-firing
needs a tripped threshold AND a material change: a different
snapshot hash (items arrived / left / changed), or the same
oldest item strictly older on substantive log growth. A poll
loop over an unchanged queue never re-fires — including the
run immediately after a firing, because the firing's own
checkpoint is non-substantive and moves neither age nor hash.
**Operator drop.** With `--deliver`, a Markdown file is
committed to the fleet's agent-inbox repo (`verdicts/`,
numbered sequentially past the highest existing NNN- file, in
that folder's verdict format: header block, `claims: COMPLETE`
inventory line, one claim section carrying the summary text and
the verification recipe; pushed when the repo has an origin).
Without `--deliver` nothing leaves the machine; the tests
deliver only into a throwaway git repo and never push.
**Finding from the tests, worth keeping.** The notifier is an
external writer: after it appends, a long-lived Sequencer
holding the same file in memory is stale, and its next append
would fork the chain (the first version of two tests did
exactly this and the chain verifier caught it). One writer at
a time; a process that wants to submit after a notification
rebuilds from the log. That is the sequencer's existing
one-writer doctrine, now exercised against a second writer.
**Suite.** Slice tests 15/15; full suite run and cold-clone
numbers are recorded in the close entry below. No existing
test was touched; nothing depends on the interim rank-tie
disposition.

## Phase 5 — slice 14: close (2026-11-02)

- **Push.** 3406bb3 (tool + tests) and 8398e93 (log + README)
  on GitHub main, over slice 13's fe965e0. Two rebase rounds
  against the landing slice-13 commits; both conflicts were
  append collisions in README.md / this log and were resolved
  append-merge (both sides kept), plus one factual correction:
  the README Phase 5 status sentence now names slices 13 and
  14 as landed.
- **Suite.** Slice tests 15/15. Full suite on the merged tree:
  221 passed, 7 skipped (the declared Probe B skips) — 198
  baseline + slice 13's 8 + slice 14's 15.
- **Cold clone.** Fresh clone of GitHub main at 8398e93:
  221 passed, 7 skipped. The CLI smoke from the clone
  (seed-demo, fire at --max-age-s 3, second run suppressed,
  --verify) reproduces the working tree's results exactly —
  the fired snapshot hash 356766a4… is identical across both
  clones, as a log-derived number must be.
- **Origin note.** The parallel clone's `origin` is the local
  ~/jacquard working repo (checked out on main by the slice
  12/13 builders), so pushes went to a `gh` remote pointing at
  GitHub directly; the local clone fast-forwards on its next
  pull. Nothing was pushed into another builder's working tree.
## Phase 5 — slice 12: the ZCode adapter (in progress, 2026-11-02)

Builder's log for slice 12, written during the work. Host
investigation came first, because the hook schema decides the
adapter's shape — and the investigation overturned two things
the opening entry above states.

- **Hook payload/output schema (empirical, captured from the
  real ZCode 3.16.3-40).** A probe hook recorded live payloads
  (fixtures land with the adapter's tests): the input is one
  JSON object carrying BOTH camelCase and snake_case spellings
  (`toolName`/`tool_name`, `toolInput`/`tool_input`,
  `hookEventName`/`hook_event_name`, `sessionId`/`session_id`,
  `toolCallId`/`tool_use_id`), plus `cwd`, `mode`,
  `riskLevel`, `sideEffectScope`, `timestamp`, `traceId`,
  `turnId`, `transcript_path`. Tool inputs observed: Read
  `{file_path}`, Write `{file_path, content}`, Bash
  `{command, description}`. The output the host accepts is
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "allow"|"ask"|"deny",
  "permissionDecisionReason": ...}}` (the decision fields are
  visible in the shipped bundle's output schema).
- **Decision point: PreToolUse, not PermissionRequest.** With
  the probe returning `allow` from PreToolUse, Write and Bash
  executed with NO native permission prompt, and no
  PermissionRequest hook fired at all (4 PreToolUse captures,
  0 PermissionRequest). A PreToolUse decision pre-empts the
  native flow, so the adapter registers on PreToolUse alone.
- **FINDING — configuration-file hooks do not run on this
  host, in any scope, despite the vendor skill docs.** The
  diagnosing-hooks skill says configuration-file hooks "have
  no trust gate" and run with `hooks.enabled: true`. Observed
  on 3.16.3-40 (Oracle): (1) workspace `.zcode/config.json`
  hooks were blocked as `config.project_hooks.pending_trust`
  until `zcode hooks trust grant` was run for the workspace
  (a trust CLI the skill never mentions; digests are per hook
  declaration, so any config edit re-pends trust); (2) after
  the grant (`workspace_hooks_trusted_persistent`), sessions
  still logged `workspace_hook.feature_disabled` at
  session start and no hook ever fired — with the workspace
  config, with a user-scope config in `~/.zcode/cli/config.json`,
  and with `hooks.enabled: true` added to
  `~/.zcode/cli/setting.json` (both test files removed
  afterwards; the host was restored). The bundle's admission
  code gates workspace hooks on a host-supplied
  `workspaceHookTrustEnabled` flag that the interactive TUI
  host does not supply in this build (the one construction
  passing it is a background-task host). (3) **Plugin hooks
  DO run**: the same probe, packaged as a local plugin
  (`.zcode-plugin/plugin.json` with `"hooks":
  "hooks/hooks.json"`) and installed from a local marketplace
  via `zcode plugins`, fired for Read/Write/Bash in a live
  interactive session. Consequence for this slice: the
  adapter ships BOTH surfaces — the workspace config snippet
  (the documented surface; it is what the config.example
  promises, and it will take effect wherever config hooks are
  enabled) and a plugin package carrying the identical hook
  registration, which is the surface the live run uses.
  Recorded here rather than engineered around silently.
- **Profile (src/jacquard/coding_agent.py).** Four words
  against the profile checker, following booking.py's pattern:
  `agent-read` (pure — Tier-P `get`; computed effects []),
  `agent-write` (emits `write`), `agent-shell` (emits
  `dispatch` with the executor's `{"cmd": [...]}` action
  shape), `agent-network` (emits `send`). Install asserts the
  kernel-computed effects equal the profile's table. Policy is
  data (`TOOL_CLASSES`): reads fast-path; the other classes
  queue — writes/shell by carrying a `notify` request beside
  the real request (the booking flow's mechanism; `notify` is
  policy/1-protected), network on its own `send` effect. An
  active learner standing rule for the shape overrides the
  queue through the sequencer's existing rule hook. Approval
  consumption is one-shot and in the log: a release authorises
  exactly one later identical action, and consuming it
  publishes a sense entry, so replay shows the whole story.

## Phase 5 — slice 12: close (2026-11-02)

- **Shipped.** `src/jacquard/coding_agent.py` (the profile:
  four words, policy as data, one-shot approval consumption),
  `adapters/zcode_hook.py` (the PreToolUse hook process;
  fail-closed on adapter error; latency sidecar on every
  invocation), `adapters/zcode/` (plugin package + install /
  uninstall scripts, the workspace `config.example.json`, and
  a README with the queue story and the redaction posture),
  real-payload fixtures under `tests/data/zcode/` with a
  provenance note, 28 adapter/profile tests, and the live-run
  record in `docs/slice12-live-run.md`.
- **Integration note (provenance of two design points).** A
  parallel completion pass landed changes in this slice's
  working clone mid-run (hook +80 lines, one test re-aimed);
  they were verified (full suite, plus a second live run) and
  integrated, not silently absorbed: (1) tools outside the
  four governed classes get NO hook output — the host's own
  permission flow governs them — because a deny would break
  host bookkeeping tools the profile does not model; passes
  are still counted in the sidecar, and fail-closed still
  holds for governed classes and for adapter errors; (2) on
  PostToolUse / PostToolUseFailure the hook reports a released
  shell action's outcome against its action machine, so the
  log records what actually ran. The registration surfaces
  gained the Post events so (2) is live, and run 2 of the
  live-run record exercises it — including its attribution
  nuance for identical repeated commands (oldest-first
  confirm), recorded in that document.
- **Live evidence (docs/slice12-live-run.md).** In a real
  interactive ZCode session: a Read fast-pathed (4.1 ms
  decision), a Write and a Bash each queued with proposal id
  + binding hash quoted back by the agent, were approved
  hash-bound via `tools/jq.py`, and their identical retries
  were allowed exactly once each; the file was created, the
  program ran, the queue drained, and every proposal's
  `jq replay` ends closed. Fast path measured over 60
  synthetic Read proposals: 43.65 ms median wall per hook
  invocation (8.34 ms median decision inside it), p95
  49.19 / 13.10 ms (`docs/slice12-latency.json`).
- **The V2 contrast, as it actually played out.** ZCode's
  hook is synchronous, so the queued action itself blocks —
  but the agent was never stuck: the deny reason carried the
  queue coordinates, the operator decided the batch in one
  CLI pass, and the retry fast-pathed on the consumed
  approval. Nothing timed out into a rejection (Permit's
  shape), and no permanent allow-rule was created (the
  incumbent alternative): one approval authorised exactly one
  execution, and the next identical action queued again,
  ready to be governed by a standing rule when the learner
  compiles one.
- **Host state after the slice.** The demo plugin and the
  probe plugin were uninstalled and their marketplaces
  removed; the workspace trust granted to the probe workspace
  was revoked; the global-config test files from the hook
  investigation were already removed mid-investigation. The
  demo workspace (`~/jacquard-slice12-demo`) and its kernel
  log remain on the Oracle as the run's raw record.

## Phase 5 — slice 15: the proof run (plan, stated before running, 2026-11-02)

Coordinator's plan entry, written before any run below starts.
(The earlier Phase 5 coordinator's slice-12 builder was still
running detached when this coordinator took over; it closed
slice 12 itself at 4481949, integrating this coordinator's
working-tree fixes with credit in its close entry. Slice 12
was independently verified by cold clone: 249 passed +
7 skipped at 4481949. The recovery history — the profile
commit 2eb54a5 found unpushed and divergent in the main
clone, rebased onto the slice-14 tip as 7e63586 — is recorded
here so the log holds the whole story.)

- **Window.** One sitting, 2026-11-02 ~22:50–01:00 UTC (the
  board booking's check-by), on the Oracle, zcode-app-cli
  3.16.3-40, GLM-5.3, interactive tmux sessions (the surface
  slice 12 proved end-to-end).
- **Workload (identical for both runs).** In a fresh scratch
  workspace holding only `SPEC.md`: build the tiny package it
  describes — read the spec, write three modules and two test
  files, run `python3 -m pytest -q` after each stage (the same
  command string recurs: the recurring shape), and at one
  scripted point attempt one network-fetch-and-execute shell
  command (the planted bad action, there to be denied). The
  agent is told: when a tool call is QUEUED, quote the
  proposal id, continue other work if any, otherwise wait for
  the operator's word.
- **Baseline (incumbent, same week, measured).** The same
  task, same host, plugin disabled, ZCode's native permission
  flow in build mode. Measured: number of native prompts and
  operator time spent answering them (each prompt is a
  synchronous interruption: notice, read, decide, keypress).
- **Jacquard run.** Plugin enabled (reinstalled from this
  repo for the run; the slice-12 close had uninstalled it).
  The operator decides the queue in batches with
  `tools/jq.py`, timing each pass. The planted bad action is
  denied; everything else is approved.
- **Measurements.** (1) Operator minutes per 100 governed
  actions, both runs (normalised from the run's actual count;
  n stated). (2) Queue statistics from the kernel log:
  submissions, queues, approvals, denials, fast paths, passes.
  (3) The rules question, tested not asserted: after the run,
  the shipped Learner pipeline (mine candidates -> register ->
  advance through shadow/canary) is run against the proof
  log, and what it actually does with the recurring queued
  shape is reported verbatim — whether the queue would shrink
  as approvals compile, measured, not assumed. (4) Safety
  ledger: every allow audited; regretted rules named and
  counted (a rule counts as regretted if, had it been active,
  it would have allowed an action the operator denied, or a
  class the operator would not have fast-pathed).
- **Report.** `docs/proof-run-2026-11-02.md` with the raw
  inputs (kernel log, latency sidecar, operator timing notes)
  under `docs/proof-run/`, so every claim re-derives from the
  log. Disagreements classified: Jacquard wrong / host wrong /
  policy gap.

## Phase 5 — slice 15: close, and Phase 5 verdict (2026-11-02)

- **The proof run is done and reported in full:**
  `docs/proof-run-2026-11-02.md`, raw inputs in
  `docs/proof-run/` (workload spec, frozen kernel log —
  sha256 66de51cbe40ba9926b6e3ff29fc6acce9dcced41188baec11b249a55ab9d9b6f,
  hash-identical to the live log — latency sidecar, operator
  timing notes). Same task, same host, same operator, both
  flows measured the same day.
- **Headline results.** Governed actions: incumbent 8,
  Jacquard 16 (retries included). Operator interruptions:
  8 vs 3 batched passes. Operator attention per 100 governed
  actions: ≈70 min poll-bound (≈21–33 at seated latency) vs
  ≈11 min, falling with batch size. The planted
  fetch-and-execute command was approved at the incumbent's
  eighth prompt and executed (harmlessly — the URL serves
  HTML); under Jacquard it was denied in batch review and
  never ran. Safety ledger: 8 allows audited, 0 unjustified;
  0 regretted rules in force; 1 named regrettable shape (the
  shell class + effect set covers both the approved test
  command and the denied fetch-and-execute).
- **The queue does not shrink yet — measured, not asserted.**
  The shipped Learner, run on the proof log, mined one
  candidate (the write shape, support 4, dominance 100%),
  predicted outcome "queue"; it reached shadow and changed
  nothing: repeat submissions of approved actions queued
  again. The learner trains on the policy's primary outcomes,
  not the operator's release/reject decisions, so approvals
  cannot compile into standing rules for the queued classes.
  Recorded as the phase's headline policy gap (proof-run doc
  §"Does the queue shrink"), with the fix direction stated
  and deliberately not built: it is Phase 6 scope.
- **Coordinator's verification of slice 12** (independent of
  its builder): cold clone of main @ 4481949 re-ran
  249 passed + 7 skipped; the coordinator's own headless arc
  (queue → hash-bound approve → one-shot consumption allow)
  reproduced the kernel side end-to-end, and the headless
  host anomaly after an allow is recorded in
  `adapters/zcode/README.md`.
- **Phase 5 verdict.** Beachhead 1 stands: a live adapter on
  a real coding agent (slice 12), the operator's verbs over
  the network with CLI-identical results (slice 13), batched
  queue notifications (slice 14), and a measured proof run
  (slice 15) showing the composition beating the incumbent
  permission flow on operator attention, with a complete
  replayable record and the one dangerous action stopped.
  The named deficit — operator-trained rule compilation for
  queued shapes — is the first item a Phase 6 charter should
  carry. Per the charter, the lane stops here: beachheads 2
  and 3 are separate authorisations.


---

# Phase 6 — the operator-trained learner + the `any` hazard (2026-11-02)

Charter: BUILD-BRIEF-PHASE6.md (Casey, 2026-11-02 14:04 AKST).
Two slices: 16 (operator-trained learner — approvals compile
into standing rules for queued shapes, the Phase 5 headline
deficit) and 17 (close the `any`-quotation computed-effects
hazard Phase 4 recorded, spec-first at 0.4). Oracle booked for
lane jacquard-build (agent-inbox aa5c174). Rank-tie disposition
stays interim; beachheads 2/3 untouched.

## Slice 16 — design, recorded before building

Read from the code, not the summaries (learner.py, sequencer.py,
coding_agent.py, the frozen proof log):

- Operator decisions are already first-class log citizens:
  release_queued / reject_queued write decision entries with
  `releases` / `rejects` plus `released_by` / `rejected_by`.
  The wait-pump's re-decisions also carry `releases` but NO
  `released_by` — so the operator label join is exact:
  a queued item's label is the follow-up decision carrying its
  id in releases/rejects WITH the actor field present.
  Expired items (either expirer) carry no label.
- The join is per proposal: the first primary decision per
  proposal id (release/reject/expire follow-ups are not fresh
  evidence — the existing primary filter), joined with the
  first operator follow-up naming it.
- Shapes gain a fourth component, the SIGNATURE: a pure
  function of the queued decision's request list, stated in
  spec §12. dispatch -> a command skeleton (shell -c unwrapped,
  split on shell operators; per segment the program basename
  plus abstracted tokens: flags keep their name, URLs become
  <url>, paths <path>, numbers <num>, bare words stay literal);
  write -> the target unit's file extension; send -> the
  channel host; every other verb -> empty detail. On the proof
  log this splits the named regrettable shape three ways:
  [python3,-m,pytest,-q] (released) vs the env-check triple
  (released) vs [curl,-s,<url>]|[sh] (rejected). Proposals the
  gate decides directly carry the empty signature — the
  signature discriminates within the queued population, which
  is the population operators govern.
- Mining: the policy pass is unchanged in method (it now
  groups by the refined shape; non-queued shapes have empty
  signatures, so existing behaviour is preserved). A second,
  operator pass groups joined decisions whose label source is
  the operator by refined shape; support is the count of
  LABELLED instances; the dominant label (>=80%) becomes the
  prediction (released -> allow, rejected -> deny); origin is
  "operator" and is part of the rule identity hash, because
  the scoring basis differs by origin.
- Scoring: policy-origin rules score exactly as before
  (against policy_outcome / primary outcomes). Operator-origin
  rules score ONLY on operator-labelled samples of their
  shape after the stage marker, and rule-made decisions are
  excluded (a decided_by sample is not independent evidence —
  it never queued, so no operator judgement exists). A later
  operator reject of the shape is a deny-labelled sample:
  disagreement, counted against the rule — the feedback loop
  closes in both directions through the ordinary demotion
  path. Quarantine is NOT built: demotion-from-operator-
  feedback is real via check_demotions on these samples, so
  the Phase 2 note stands (quarantine remains an operator
  lever) — recorded as the brief's either/or, answered.
- The rule hook learns the live signature: the sequencer's
  two rule_decider call sites pass the proposal's requests;
  operator-origin records match on signature equality,
  policy-origin records match as before (signature ignored —
  their shapes were mined over the directly-decided
  population). The recogniser word grows the signature check
  (its input map is {class, effects, signature}); it stays
  pure, computed effects [].
- Spec version: slice 16 opens 0.4 (the §12 revision);
  slice 17 completes 0.4 (§§4-5). Vectors regenerate at each
  landing; the changelog records 0.4 as a two-step landing.
- One deliberate format note: the rule record's shape dict
  gains "signature" (a list, [] when empty). The Phase 2
  mining test pins the shape dict exactly; it is updated to
  the new spec'd format — an extension, not a relaxation:
  the assertion stays exact.

### Slice 16 — implementation (2026-11-02)

Built as designed above. The pieces, in landing order: spec
§12 rewritten and the version bumped to 0.4 (SPEC.md title,
§2/§3 version literals, `SPEC_VERSION`, the seal, the TS
implementation's constants, vectors and both conformance
fixtures regenerated — the replay fixture by re-running the
gpu-queue replay through the 0.4 kernel: 3,295 entries, queue
order and event record still matched exactly); then
`learner.py` (signature machinery, the joined-decisions view,
two-pass mining, origin-relative scoring, the signature-aware
recogniser and hook) and the sequencer's two rule-decider call
sites (requests now passed through); then the tests.

Verified on the real proof log before any test was written:
the signature splits the regrettable shape three ways
(pytest / env-check / curl|sh skeletons all distinct), the
join labels all eight queued items (seven releases, one
reject), and mining the frozen log alone already yields the
write candidate (operator origin, support 4, predicted allow).

Results: `tests/test_operator_learner.py`, 8 tests — signature
splitting and abstraction, the label join (including the
pump-release exclusion), the operator mining pass (released →
allow candidate, rejected → deny candidate, expired → no
candidate), the replay acceptance (candidate reaches shadow,
climbs promote/activate on rehearsal rounds, then auto-decides
the repeated write with `policy_outcome: queued` recorded;
the fetch-and-execute resubmission queues undecided and is
covered by no release candidate), exact-shape-only firing,
canary-era rejects blocking activation, and post-activation
rejects demoting an active rule to `demoted`. Full suite:
**257 passed, 7 skipped** (249 + 8 new; the one existing-test
edit is the shape-dict format extension recorded in the design
entry). TS conformance under 0.4: 7 PASS / 3 SKIP, the
pre-bump pattern.

Two incidents worth the record. (1) The first dry run of the
replay scenario opened the frozen proof log through a
file-backed `Log` — and the sequencer APPENDED its rehearsal
entries to the evidence file (163 lines, hash changed). The
fixture was restored byte-identical from git (sha256 back to
66de51cb…) and the replay test now works on a tmp copy and
asserts the fixture's hash at the end. A file-backed log is a
live log; frozen evidence is copied before it is folded.
(2) The promotion API is two calls, not one (`promote`:
shadow → canary; `activate`: canary → active) — the design
entry's "promote through the stages" is shorthand for both,
and the demotion target stage is named `demoted`, not shadow;
the tests assert the real names.

Eval thinness, stated plainly: on the proof log the write
candidate's offline eval passes on ONE held-out operator
sample (the 70/30 cut of nine joined decisions is that
sparse). The shadow and canary stages each required three
further concordant operator verdicts before activation, which
is where the evidence actually accumulated — the ladder's
design intent, but the eval number should not be quoted
without its sample count.

Quarantine: NOT built (per the design entry's reasoning —
demotion from operator feedback is real through the scoring
basis; quarantine remains an operator lever, as before).

Remaining in this slice: the live proof run. Its plan is
committed in the next log entry, before it runs.

### Slice 16 — live proof run plan (committed before running)

Purpose: the brief's second acceptance — a second bounded
proof run in the Phase 5 shape, showing the queue SHRINKING
against Phase 5's ≈11 operator-minutes per 100 governed
actions, with the learned rules in force and zero regretted
rules.

Setup: scratch root `~/jacquard-phase6-proof/`; ONE kernel log
(`kernel.jsonl` at the root) shared by both sessions via
`$JACQUARD_LOG`; the ZCode adapter installed from this repo
(plugin surface, as slice 12); ZCode interactive in tmux;
operator decisions via `tools/jq.py`; operator timing noted in
the Phase 5 format. Session workspaces `s1/` and `s2/` (fresh
code dirs; the log — and therefore the learned rules — is
shared, as it would be for one operator supervising one agent
across projects).

Workload (both sessions, the same spec, committed as
`docs/proof-run-2/SPEC.md` when the run lands): a tiny package
`tidelog`, six files written one at a time
(`tidelog/__init__.py`, `model.py`, `parse.py`, `report.py`,
`tests/test_parse.py`, `tests/test_report.py`), with
`python3 -m pytest -q` run after EACH file — the repetition is
the point: six writes and six test runs of two signatures. One
environment-check shell command near the start (a signature
seen once). One planted fetch-and-execute step, attempted once
as the last step, as in Phase 5: it must queue and be rejected;
it is never executed.

Session 1: every governed action queues (fresh log); the
operator releases in batched passes (the planted step
rejected). Mining then runs on the session-1 log; the write
and pytest operator candidates are registered to shadow.

Learning bridge (labelled as what it is): rehearsal rounds at
kernel level — repeats of the two learned shapes submitted
through the same coding-agent profile functions the adapter
uses, against the same log, released by the operator in
batches — carry both rules through canary to active. These are
genuine queued items and genuine operator verdicts on the real
log; they are not agent-driven, and the report says so.

Session 2: the same workload in the fresh workspace. Expected:
the six writes and six pytest runs are auto-decided by the
active rules and never queue; the env-check queues (seen once,
unlearned); the planted step queues and is rejected. Queued
items: session 1 ≈ all of them, session 2 ≈ 2.

Reporting: queued-item counts per session from the log;
operator minutes per 100 governed actions for session 2
(marginal) AND amortised across session 1 + bridge + session 2,
both against Phase 5's ≈11; the regretted-rules ledger (any
active rule whose shape the operator later rejected — expected
none; the fetch-and-execute signature must be covered by no
rule, asserted from the log). Raw inputs (spec, kernel log,
timing notes, latency sidecar) land in `docs/proof-run-2/`;
the report at `docs/proof-run-2-2026-11-02.md`.

### Slice 16 — live proof run results (2026-11-02)

Ran as planned; the full record is
`docs/proof-run-2-2026-11-02.md` with raw inputs in
`docs/proof-run-2/` (507-entry log, sha256 61d96a2a…). The
headline: session 1 queued 14 of 15 governed actions (14
operator decisions in 14 passes — this agent waited per item);
session 2 queued **1 of 16** (the once-seen env-check), with
an estimated ≈3 operator-minutes per 100 governed actions
marginal against Phase 5's ≈11 baseline, and ≈20/100
amortised across the whole run — the learning is paid once
per shape.

Two findings beyond the plan. (1) The bridge's rehearsal
releases left unconsumed one-shot approvals in the log, and
the adapter (by its slice-12 order: approvals before
submission) let session 2's six pytest runs consume them — the
queue still shrank, but the pytest RULE was masked for exactly
the rehearsal count; a final pytest after the carryover was
exhausted was decided by the rule itself (seq 499). The write
rule fired directly, six times (seq 443–490). (2) Session 2's
planted step never queued and never reached the operator: the
adapter's rejected-twin rule denied it on sight of session
1's rejection. Zero curl executions in the log. Regretted
rules: none.

Slice 16 is complete: replay acceptance in the suite, live
acceptance here, both with evidence. Remaining Phase 6 work:
slice 17.

### Slice 17 — design (2026-11-02)

The hazard (Phase 4, probe (f), quarantined in
`tests/probes/fold_experiment.py`): an extension dictionary
implementing a quotation form `{"any": [token]}` inherits the
stock token walk, which descends only into `if`/`else` lists —
so a Tier-E verb inside a quotation computes NO effects while
evaluation emits the request. C2 fails for that form. The
stock kernel itself never accepted such a body, but only
incidentally: its evaluator raises FIELD "bad token" for any
dict that is not a literal or a conditional. An incidental
failure under the wrong name is not a spec property, and the
walk's narrowness is the real defect: any form added later
inherits silent under-accounting.

The fix is at both levels, spec first (SPEC §§4–5, this
slice): the token forms are exactly the three listed; any
other dict form is REFUSED(SPEC) at definition time with the
form's key named; the effects walk descends into every token
position of every form except inside a literal value (data —
and this language has no form that evaluates data as code, so
the exclusion cannot be turned into an evaluation path); C2 is
stated in §4 with the quotation case included: quotation
defers evaluation, never accounting.

Implementation, in `dictionary.py`:

- `_walk_tokens` descends into every dict token's values
  except a `lit` value, and into bare lists. Accounting can
  then never undercount by hiding in a form: the walk is
  form-agnostic.
- The stock `_simulate`/`_exec` treat a dict token that is
  neither the lit form nor the if form as Refusal("SPEC", …)
  naming the form's key — a deliberate refusal under the
  spec's name, replacing the incidental FIELD "bad token" for
  dict forms (non-dict bad tokens keep FIELD).
- Consequence for the quarantined prototype: `FoldDictionary`
  inherits the descending walk, so its `any-write` definition
  now computes {"write"} — accounted even in the extension —
  while the stock kernel refuses the same definition SPEC,
  naming `any`. Both horns of the brief's either/or hold, each
  at its level.

Probe disposition: the two probe-(f) tests that pinned the
hazard's existence are re-aimed at the closure, as declared
supersessions with their reasons, in the probe file and in a
dated addendum appended to
`docs/completeness-probes-2026-11-02.md` (appended, never
rewritten). The adversarial battery is a new test file:
the original probe case both ways, nested quotations, a
quotation inside an if branch, composition smuggling, a
hybrid dict form, a literal carrying verb-shaped data (must
stay inert), and an evaluation-time forgery. TS: definitions
remain SKIP in the fold-scope checker; `conformance/ts/
GAPS.md` gains the 0.4 accounting rule in its definitions
entry.

### Slice 17 — implementation and Phase 6 close (2026-11-02)

Built as designed. Spec §§4–5 first (token forms enumerated;
unknown dict forms REFUSED(SPEC) with the form named; the
walk's descent rule; C2 stated with the quotation case), then
`dictionary.py`: `_walk_tokens` is form-agnostic (every dict
value except a pure literal's, plus bare lists), and the
stock simulation/evaluation paths refuse non-lit/non-if dict
forms as SPEC naming the form's first sorted key, replacing
the incidental FIELD "bad token" for dict forms only. The
hazard case now lands on both horns: stock define of the
probe's `any-write` → REFUSED(SPEC) naming `any`; via
`FoldDictionary` → accepted with computed effects `["write"]`.

Acceptance battery: `tests/test_quotation_battery.py`, 9
tests (original case both ways, nested quotations, quotation
in an if branch, composition smuggling plus the positive
union case, hybrid dict forms, verb-shaped literal data
inert, forged body refused at evaluation). The two probe-(f)
tests are re-aimed as declared supersessions;
`fold_experiment.py`'s docstring records its partial
supersession; the findings document gains a dated addendum
(appended, §§1–6 and the Phase 5 addendum untouched); TS
conformance records the 0.4 rule at GAPS item 17 with
definitions still SKIP, and the checker reproduces 7 PASS /
3 SKIP. Full suite: **266 passed, 7 skipped** (257 + 9).

Phase 6 close. Test delta across the phase: 249 + 7 skipped
→ 266 + 7 skipped (+17 net: 8 operator-learner, 9 quotation
battery; the 2 probe re-aims and 2 format-extension updates
— the learner shape record and the version literals —
are assertion-preserving in intent and recorded where they
sit). Spec 0.4 is complete: §12 (slice 16) and §§4–5
(slice 17). Tagged v0.4.0.

What V4 still does not cover, stated once more at the close:
the learner mines from decisions the operator actually made
on shapes the gate actually queued. It does not learn from
actions the policy allows outright (nothing to govern), from
queued items the operator lets expire (no label — by design:
an undecided item teaches nothing), or across producers
(shapes are per-producer). Signatures discriminate by command
skeleton, file extension and host; two commands differing only
in an abstracted token (a path, a number, a URL) are one
shape, and an operator who needs them split needs a finer
signature function — a spec change, not a configuration.
Within those bounds the loop the proof run found open is
closed in both directions: releases compile into rules, and
rejects — before activation as a block, after it as
demotion — count against them.

# Phase 7 — anchoring + the full TS port (2026-11-02)

## Slice 18 — design, recorded before building (2026-11-02)

The charter (Casey's Phase 7 authorisation): slice 18 is
chain-head anchoring — signed checkpoints of (log length, head
hash, spec version) published outside the kernel's store, so a
presented log can be verified against history the operator cannot
silently rewrite. This is beachhead 2's core mechanism and the
void scan's V3: of 25 surveyed products, immutability was claimed
by some and mechanised by none. Slice 19 (the full TS port) is
the other half of the phase and is not this slice; here the TS
checker gets version bookkeeping only.

The defect, stated plainly: section 2's hash chain proves a log
is self-consistent, not that it is *the* history. Whoever holds a
log can rewrite a middle entry and recompute the chain from there
on; the forgery passes the kernel's own chain verification
perfectly. The slice's acceptance fixture is exactly that attack,
built against the frozen Phase 6 proof log (below).

Spec first, as always: new section 15, spec 0.5. The decisions,
with their reasons:

- *Checkpoint document.* A signed body with exactly eight keys
  (`format`, `log_id`, `label`, `checkpoint_seq`, `log_length`,
  `head_hash`, `spec`, `prev_checkpoint`); any extra or missing
  key is not a checkpoint. What is signed is the canonical bytes
  of the body alone. The envelope (`body` + `pubkey` + `sig`) is
  the file form. Exactness mirrors the bundle format's discipline
  (section 14): a verifier should never have to guess which
  fields were covered by the signature.
- *Checkpoint chain.* `prev_checkpoint` hash-chains each log's
  checkpoint sequence, so a published checkpoint cannot be
  dropped or reordered without breaking a chain the verifier
  recomputes — the transport's append-only discipline gets a
  cryptographic second witness.
- *Log identity.* `log_id` is the genesis entry's hash. This is
  the only identity derivable from a log that already exists —
  the frozen proof logs carry no log-id field, and an identity
  that cannot be computed for them retroactively would exempt
  exactly the logs most worth anchoring. The limitation is
  stated in the spec, not hidden: `log_id` names a lineage, two
  logs sharing a genesis share it, and identity does no security
  work — the (`log_length`, `head_hash`) pair binds the prefix.
- *No signed timestamp.* The body carries no wall-clock field.
  Jacquard has no trusted clock (the jqnotify slice established
  this the hard way: the log's clock is the log), and a signed
  timestamp would be an operator assertion dressed as evidence.
  Existence-at-a-time rests on the transport's publication
  record (the git commit that first carries the checkpoint).
- *Signing.* Ed25519, via the `cryptography` package — the
  anchor tooling's only non-stdlib dependency, confined to that
  tooling; the kernel stays zero-dependency and imports no
  signing code (the anchor module is not exported from
  `jacquard/__init__`, so `import jacquard` never requires it).
  Private key at `~/.jacquard/anchor-key.ed25519`, mode 0600,
  outside every repo; the tool refuses to overwrite an existing
  key and refuses a key path inside a version-controlled tree.
  Compromise and rotation stories are stated in the spec
  (15.3), including the uncomfortable part: with no trusted
  clock, "issued before the compromise" rests on the transport
  record, not the document.
- *Cadence.* An operator-run verb, never automatic — anchoring
  is deployment work, like execution (section 10.5). The spec
  recommends: end of session / proof run, at least daily while a
  log grows, always before a third party relies on the log. The
  gap is named, not hidden: entries past the last anchored
  length are the *unanchored tail*, and verification reports its
  length numerically.
- *Verification outcomes, never a bare boolean:* VERIFIED
  (fully anchored), VERIFIED-TO-ANCHOR with anchored prefix and
  tail lengths stated separately, UNANCHORED (no applicable
  history — a statement, not a failure), FAILED naming the first
  divergent checkpoint (or the history / internal-chain failure,
  distinctly). An extension of an anchored log is
  VERIFIED-TO-ANCHOR, not a forgery; truncation below an
  anchored length is FAILED, never a "tail".
- *Transport.* Transport-agnostic in the spec; first transport
  is a new, separate public git repo,
  `SuperInstance/jacquard-anchors` — separate so the witness
  history is not the witnessed history's own repo. One file per
  checkpoint (`checkpoints/<log_id>/<seq>.json`), one commit per
  checkpoint, adds only: never amend, rebase or force-push.
- *Golden vector.* The vectors gain an `anchor` section: one
  checkpoint over the vector entry chain under a published test
  key (seed recorded in the vectors; Ed25519 signing is
  deterministic, so the signature is a stable vector). The TS
  checker declares it SKIP (verifier work, not fold work), with
  the rule recorded in GAPS — the deep TS port is slice 19.

Version mechanics follow the 0.4 pattern (commit 907e5ac):
SPEC_VERSION + seal in both implementations, golden vectors
regenerated, the full-log fixture regenerated, and the replay
fixture regenerated by re-running the gpu-queue replay through
the 0.5 kernel (3,295 entries expected; queue order and the
event record must still match exactly). Frozen logs (proof runs
1 and 2) keep their 0.4 entry spec — anchoring a 0.4 log with a
0.5 checkpoint is the normal case, and the spec says so.

Acceptance, stated before building: (1) the true proof-run-2 log
verifies against two published checkpoints (mid-log and full);
(2) a forged variant — one decision outcome flipped mid-log, the
chain recomputed from there so the forgery is fully
self-consistent — passes internal chain verification and FAILS
anchor verification naming the first divergent checkpoint; the
fixture and its provenance note are committed under `tests/`;
(3) an extended log reports its unanchored tail exactly;
(4) `docs/anchor-drill.md` lets a fresh verifier, given only the
public anchor repo, the spec and a presented log, reproduce all
of it cold; (5) cold clone: Python suite + TS checker green.
The rank-tie interim disposition is untouched by this slice.

### Slice 18 — implementation and close (2026-11-02)

Built as designed, in the stated order: spec §15 first
(18a30a1), version mechanics (550970a), the anchor module +
CLI (a1ecaa7), the forged fixture + battery (1a114f6), a
consistency fix (f77b924), the drill (1fa191c), and this docs
close. Evidence for each acceptance item from the design entry:

1. *True log verifies against published history.* Key generated
   on the Oracle at `~/.jacquard/anchor-key.ed25519` (mode 0600;
   public key `1aa240ac…b3072be5`). Anchor repo
   `SuperInstance/jacquard-anchors` opened at 51a2f73 (README +
   pubkey.txt); checkpoint 0 (length 250, head 9a3f33a2…)
   committed 1f1309b; checkpoint 1 (length 507, head 1e02bd86…)
   committed 89a6de3 — one commit per checkpoint, adds only.
   Verified from a *fresh clone* of the anchor repo: outcome
   `verified`, 507/507, tail 0, exit 0.
2. *The forgery.* `tests/data/forged/proof-run-2-forged.jsonl`:
   seq 100's outcome flipped `allow` → `deny`, chain recomputed
   from seq 100 (generator + PROVENANCE.md committed). It loads
   through the kernel's `Log` class and `verify_chain()` returns
   true; against the published history it FAILS at checkpoint 0
   (expected head 9a3f33a2…, actual de47470f…), exit 1, with
   `internal_chain_ok: true` in the same result. Both directions
   are asserted in `tests/test_anchor.py` (18 tests), alongside
   tail-exactness (250 anchored / 257 tail against the
   mid-checkpoint alone), extension-is-tail, truncation-is-
   failure, dropped-checkpoint and bad-signature history
   failures, wrong pinned key, keygen refusals (overwrite,
   in-repo path, loose mode), and a fresh-interpreter check that
   `import jacquard` pulls in neither the anchor module nor
   `cryptography`.
3. *Drill.* `docs/anchor-drill.md`, every step executed verbatim
   before commit — including the `sed -n '250p'` spot check and
   the three exercises beyond the headline pair (tail subset,
   truncation at 300 → FAILED naming checkpoint 1, the Phase 5
   log → UNANCHORED, exit 3).

Findings during the build, none smoothed: (1) exercising the
drill's truncation step caught a wart in my own verifier — on a
prefix failure it reported `anchored_length` advanced but
`unanchored_tail` still at its initial value, arithmetically
inconsistent numbers a cold verifier would trip on; fixed
(f77b924) so lengths recompute on every return path, with a
regression assertion. (2) A first-draft test asserted
`not hasattr(jacquard, "anchor")` — false reasoning: importing a
submodule anywhere in the suite sets it as a package attribute.
Replaced with the fresh-interpreter check, which tests the
actual invariant. No test was weakened in either case; both
fixes strengthened the assertion.

Deviations from the design entry and from prior-phase patterns,
with reasons: (a) TS SKIP count moves 3 → 4 — the new
`vectors.anchor` SKIP, recorded at GAPS item 18; the alternative
(a TS verifier in this slice) is slice 19's charter, not a
bookkeeping dodge. (b) `pyproject.toml` version bumped
0.3.0 → 0.5.0: the 0.4 release left it at 0.3.0 while the spec
moved to 0.4, a stale-version wart this close corrects rather
than repeats (no tag is cut by this slice; v0.5.0 belongs to
the phase close, after slice 19). (c) Spec §15.5's genesis step
is realised as *selection* semantics: a history whose `log_id`
names a different genesis is not applicable to the presented
log, so the outcome is UNANCHORED (with `internal_chain_ok`
still computed and reported), not FAILED — FAILED is reserved
for histories that claim this log and fail it. (d) The replay
fixture's gzip is back to the ~1.48 MB indent-1 form (the 0.4
regen's compact dump was the outlier); content is the same
3,295 entries re-run through the 0.5 kernel, dispatch record
exact.

Rotation posture at close: the verifier takes a key schedule
(CLI: `--pubkey` plus `--rotation-seq` / `--rotated-pubkey`),
and no rotation has occurred. The private key's only copy is
the Oracle file named above; a stage-and-scan of every push in
this slice (`git log -p` grep for key material at close) found
none in either repo — the strings that match "anchor-key" in
the history are prose stating where the key lives, as the spec
requires.

Slice 18 is complete. Remaining Phase 7 work: slice 19 (the
full TS port, including a TS §15 verifier that retires the
anchor SKIP). Suite at close: **285 passed, 7 skipped**; TS
conformance: **7 PASS, 4 SKIP**. Cold-clone evidence is
recorded in the verification addendum the coordinator runs at
phase close; the pre-close fresh-clone runs of both suites were
green from this tree (see the close commit's verification).

### Slice 18 — cold-clone verification addendum (2026-11-02)

Run after the close commit (fec4206) was pushed, from fresh
clones of both public repos, on the Oracle:

- `git clone https://github.com/SuperInstance/jacquard.git` at
  fec4206 → `python3 -m pytest -q`: **285 passed, 7 skipped**.
- Same clone, `conformance/ts`: `node check.ts` → **7 PASS,
  4 SKIP** (definitions, state, anchor, senses), exit 0.
- Same clone, drill against a fresh clone of
  `jacquard-anchors` with the pubkey taken from that clone's
  `pubkey.txt`: true proof log → `verified`, 507 anchored,
  tail 0; forged fixture → exit 1, `failed` at checkpoint 0,
  `internal_chain_ok: true`.
- Secret scan of the slice: `git log -p` of both repos greps
  zero for any PEM private-key header and zero for a fragment
  of the operator key's PEM body; the key filename is tracked
  in neither repo; the key file itself is mode 0600 at
  `~/.jacquard/anchor-key.ed25519` on the Oracle and nowhere
  else.

# Phase 7 — slice 19: the full TypeScript port (2026-11-02)

## Slice 19 — design, recorded before building (2026-11-02)

This is a **port, not a clean-room reimplementation**. The
distinction matters and is stated plainly so nobody misremembers
it later: Phase 3's spec-only rule applied to the fold checker
(`conformance/ts/jacquard.ts`, already landed — its author never
read the Python source, and its GAPS.md is the record of that
experiment). Slice 19's charter is the opposite method: the
Python source in `src/jacquard/` is the reference behaviour and
`spec/SPEC.md` is the contract, and the TS code in
`conformance/ts/kernel.ts` is written *from* the Python —
`dictionary.py`, `sequencer.py`, `senses.py`, `learner.py`
(signatures only), `policy.py`, `anchor.py` — section by
section. Where Python and spec diverge, the standing rule
applies: divergence is a spec bug first — fix the SPEC,
regenerate the vectors, re-run both suites, record it; never
silently align the implementations.

Scope, in build order:

1. **Dictionary + evaluator** (§§4–5): definitions, the
   form-agnostic effects walk with REFUSED(SPEC) on unknown
   dict forms (slice 17 semantics, the first sorted key named),
   typed stack simulation, examples, computed effects as the
   union over expansion. Closes `vectors.definitions`.
2. **Sequencer** (§7 + §7.1 + policy gate): envelope
   validation and idempotency, submissions, decisions,
   queueing / release / reject / expire, the wait pump,
   budgets / prices / senses / checkpoints as public sequencer
   operations — reproducing the state the vectors record.
   Lifecycle *machines* are not ported: a kernel without the
   lifecycle machines installed behaves as the 0.1 kernel
   (spec §10.4), and the TS sequencer is exactly such a kernel;
   every lifecycle step in the Python reference is a no-op
   under that configuration, so the logs agree byte-for-byte
   on the drill stream. Closes `vectors.state`.
3. **Sense computation** (§11.3): the contention and authority
   methods over entry prefixes (plus the other built-in senses
   the Python module ships), reproducing the `vectors.senses`
   expected readings byte-identically, method strings included.
   Closes `vectors.senses` and GAPS item 16.
4. **Anchor verification** (§15): Ed25519 checkpoint signature
   verification and the §15.5 prefix/tail outcome logic, using
   Node's built-in `crypto` (Ed25519 is supported natively —
   no new dependency; if a real obstacle appears it is recorded
   here, not routed around silently). Closes `vectors.anchor`
   and GAPS item 18.
5. **§12.1 shape signatures**: the learner's
   `shape_signature` in TS, proven identical to the Python
   computation over BOTH proof-run corpora
   (`docs/proof-run/kernel.jsonl`,
   `docs/proof-run-2/kernel.jsonl`) by a committed comparison:
   a Python-generated expectations fixture (per queued decision:
   seq, signature, and the set hash) that `check.ts` recomputes
   from the TS side and compares exactly.

Acceptance, stated before building: (1) `node check.ts` runs
the full golden-vector suite with **zero SKIP lines**, exit 0;
(2) a cross-language drill — one fixture (dictionary
definitions and a standing-rule record defined once, plus a
proposal stream exercising allow / queue / release / reject /
expire / underdeclared / wait-true / wait-false-then-fired /
wait-expired / spend-with-price / sense / checkpoint) driven
through BOTH sequencers — produces **byte-identical logs**
(sha256 compared, evidence committed); (3) the Python suite
stays at its 285 passed / 7 skipped baseline or better;
(4) GAPS.md gains dated closure notes for items 16, 17, 18,
items 1–15 close only where a check now genuinely discriminates
the reading, and any new gap the port exposes is recorded;
(5) on all-green main, tag **v0.5.0** is cut and verified from
a fresh clone OF THE TAG (Python suite line, TS checker line,
one anchor verification of the true proof-run-2 log against
the public anchors repo — all verbatim).

Preliminary bookkeeping, landed as this slice's first commit:
an independent verifier ran `docs/anchor-drill.md` cold, passed
it, and flagged four document defects, all fixed in that
commit: (1) §2's "exactly" field list omitted the eighth
output field, `log_id` — the list now names all eight fields
with the log's id value; (2) §4 now starts from a clean
scratch directory (`rm -rf /tmp/tail-check`) and carries the
`echo "exit=$?"` line the other sections have; (3) §4's copied
layout drops the anchor repo's `checkpoints/` level — the
drill now explains at the point of use that `--checkpoints`
searches recursively, so the shallower layout is found;
(4) the drill now states its honest limit up front: it is
GUIDED, not blind — the fixture path and provenance disclose
the forgery, so it tests procedure and mechanism, not
verifier blindness. The rank-tie interim disposition is
untouched by this slice.

### Slice 19 — implementation, part 1: the port and the checker (2026-11-02)

`conformance/ts/kernel.ts` landed: the port, mirroring the
Python modules named in the design entry. Points of method
worth recording while they are fresh:

- The TS fold's decision case was aligned to the reference
  fold during the port (queued-only literal; the
  releases/rejects/expires chain is an elif chain, and a queued
  body does not also close an item). The pre-slice-19 reading
  (accepting `"queue"` as well, closing on any of the three
  fields regardless of outcome) was a GAPS-#7-era guess the
  §2.1 amendment had already superseded in prose; the replay
  and full-log fixtures contain no body that discriminates the
  two readings, so checks e–g pass under both — the alignment
  is to the reference behaviour, recorded here rather than
  silently absorbed.
- Ed25519 needed no new dependency and no workaround: Node's
  built-in `crypto` verifies Ed25519 natively once the raw
  32-byte key is wrapped in the fixed RFC 8410 SPKI prefix
  (and a seed in the PKCS#8 prefix to derive the test pubkey).
  The obstacle the design entry braced for did not exist.
- Python semantics reproduced deliberately, not approximately:
  floor division/modulo, `True == 1` equality, empty-container
  falsiness, `repr` formatting inside refusal details (those
  strings land in decision-entry `reasons`, so they are part of
  the byte record, not cosmetics), and a POSIX `shlex` for the
  §12.1 command skeleton.
- §12.1 comparison is a committed fixture, not a claim:
  `conformance/ts/gen_signature_expectations.py` computes the
  Python learner's signature for every request-carrying
  decision in both proof-run corpora (8 in proof-run, 27 in
  proof-run-2) and `check.ts` recomputes each one in TS,
  comparing item-for-item and by canonical hash.

Checker state after part 1: **13 PASS, 0 SKIP, 0 FAIL** —
a–g as before, `vectors.definitions`, `vectors.state`,
`vectors.senses`, `vectors.anchor` as real checks with the
same strictness as the Python vector tests (stored forms
compared whole; sense readings compared whole, method strings
included; the anchor signature checked both ways and the
§15.5 procedure run over the vector chain), plus the §12.1
signature comparison (h) and the stock-kernel half of the
slice 17 token-form battery (i). No spec bug was found in
part 1: every divergence encountered was a TS-side reading
corrected against the reference, not a contract defect.

### Slice 19 — implementation, part 2: the cross-language drill (2026-11-02)

One fixture, defined once (`conformance/ts/cross-drill/
fixture.json`: 7 dictionary definitions, a standing-rule
record, budgets/prices, and a proposal stream), driven through
both sequencers by twin drivers (`run_python.py`, `run_ts.ts`),
compared by `cross_drill.py`, evidence committed in
`EVIDENCE.txt` next to both logs and both verdict streams.
The stream was designed to make byte-identity earn its keep:
protected-effect queueing with release / reject / expire, a
priced spend (alice 100 − 5×3 = 85), an operator spend with no
prior grant (operator −6, the budget key created by the spend),
a define-in-proposal, an underdeclared fault decision, a
suspension deny, the full wait repertoire (queued-then-fired
by a later write, a guard that starts refusing mid-wait —
recorded once as `wait-guard-refused:FIELD` with
`wait_refusal_at` — then fires when the divisor lands, a
deadline-0 waiter expired by its own submission's pump, and a
wait satisfied at submission), idempotent resubmission, a
sense, and a closing checkpoint.

Result: **38 ops → 52 log entries; python log sha256
0cde737c…, ts log sha256 0cde737c… — byte-identical; verdict
streams byte-identical too** (sha256 021bce65…), including the
two refusal verdicts' detail strings (the `any` probe refused
SPEC by name, the misdeclared definition refused
UNDERDECLARED, in both languages word-for-word).

The TS anchor CLI (`conformance/ts/verify-anchor.ts`) was run
against the public anchors repo before the docs close: true
proof log `verified` 507/507 tail 0 (exit 0); forged fixture
`failed` at checkpoint 0, `internal_chain_ok: true` (exit 1);
tail subset `verified_to_anchor` 250/257; truncation at 300
`failed` naming checkpoint 1; Phase 5 log `unanchored`. Every
outcome and every failure field matches the Python tool.

GAPS.md gained the slice 19 closure section: items 16, 17, 18
closed; items 3, 7, 10, 11, 14 closed with the discriminating
check named (item 3's closure corrects the original "caught
by: none" — the golden entries discriminate the escaping
reading and had since the non-ASCII entry landed); item 13
closed in part, kinds named; items 1, 2, 5, 15 left open with
the reason (no discriminating fixture exists). One new
recorded item, filed as port scope rather than a spec gap:
the TS sequencer's machine-envelope refusal — §10 is
fold-covered only, and the log records exactly where that
boundary sits. No spec bug was found in part 2 either: the
drill agreed byte-for-byte on the first complete run, after
part 1's fold alignment.

### Slice 19 — close, and Phase 7 close (2026-11-02)

All acceptance items from the design entry, with evidence:

1. **Zero SKIPs.** `node check.ts`: 13 PASS, 0 SKIP, 0 FAIL,
   exit 0 — run on the builder's machine and re-run on the
   Oracle against the pushed tree (identical output).
2. **Cross-language drill.** 38 ops → 52 entries; logs
   byte-identical (sha256 0cde737c…), verdicts byte-identical
   (sha256 021bce65…); evidence committed under
   `conformance/ts/cross-drill/` and regenerated cleanly on
   the Oracle (no tree drift after the rerun).
3. **Python suite.** 285 passed, 7 skipped on the Oracle —
   the baseline, unchanged; the port touched no Python code.
4. **GAPS.** Closures and the port-scope note are in
   `conformance/ts/GAPS.md` (slice 19 section): 16/17/18
   closed; 3/7/10/11/14 closed with discriminating checks
   named; 13 closed in part; 1/2/5/15 left open, with reasons.
5. **Spec bugs: none.** The standing rule was not triggered —
   no divergence survived contact with the reference as a
   contract defect. The one real reading change (the fold's
   decision chain) was a TS-side guess from the GAPS-#7 era
   that §2.1 had already superseded in prose; it is recorded
   in part 1 and in GAPS #7's closure, not in the spec.

Deviations, with reasons: (a) the drill's "standing rules
defined once" is realised as one standing-rule *record*
appended identically in both kernels plus its recogniser
definition — the learner pipeline that *creates* rules
(§§12.2–12.4, machine-staged) is outside the port's charter,
so the drill pins the record's fold and the recogniser's
dictionary behaviour, which are the parts the two kernels
share; the §12.1 signature — the learner piece the charter
does name — is proven over both real corpora instead.
(b) The TS sequencer refuses `machine` envelopes with a
scope-naming SPEC verdict (GAPS, port scope): §10 is
fold-covered (check g), not sequencer-ported, and naming the
boundary in the verdict itself keeps the divergence honest
at the exact surface where it occurs.

Phase 7 is complete: anchoring (slice 18) made the record
verifiable without trusting its holder, and the port
(slice 19) made it reproducible without trusting its
implementation. Tag **v0.5.0** is cut at this close; the
tag-clone verification (Python suite line, TS checker line,
TS anchor verification of the true proof-run-2 log against
the public anchors repo) is recorded in the addendum that
follows it, as with slice 18.

### Slice 19 — tag-clone verification addendum (2026-11-02)

Run after the close commit (5442cbf) was tagged **v0.5.0**,
from fresh clones of both public repos, on the Oracle:

- `git clone --branch v0.5.0` of `SuperInstance/jacquard`
  (at 5442cbf) → `python3 -m pytest -q`: **285 passed,
  7 skipped**.
- Same clone, `conformance/ts`: `node check.ts` → **13 PASS,
  0 SKIP, 0 FAIL**, exit 0.
- Same clone, TS anchor verification of the true proof-run-2
  log against a fresh clone of `SuperInstance/jacquard-anchors`
  (pubkey taken from that clone's `pubkey.txt`):
  `node conformance/ts/verify-anchor.ts docs/proof-run-2/kernel.jsonl
  --checkpoints <anchors clone> --pubkey 1aa240ac…b3072be5`
  → outcome `verified`, `log_length` 507,
  `anchored_length` 507, `unanchored_tail` 0,
  `checkpoints_checked` 2, `internal_chain_ok` true,
  `failure` null, exit 0.
- Secret scan of the slice (60a2321..5442cbf): `git log -p`
  greps zero for any PEM private-key header; no key file is
  tracked; the anchor private key remains mode 0600 at
  `~/.jacquard/anchor-key.ed25519` on the Oracle and nowhere
  else (the single diff match for its filename is prose
  stating where it lives, as the spec requires).

### Slice 21 — design entry (2026-11-02): beachhead 2 remainder

Phase 8 slice 21, three pieces: key management as a product
surface, PII/redaction as a sealing view, and a compliance
mapping. This entry is the design, written before the code, as
the brief requires (§15.3 is rewritten in the same commit, so
the spec states the design before the implementation exists).
Starting state: main@458851d, spec 0.5, Python 285 passed +
7 skipped, TS 13/0/0; the live anchors setup is one unencrypted
operator key, checkpoints seq 0/1 over proof-run-2/kernel at
lengths 250/507 under pubkey 1aa240ac…b3072be5.

**Version: spec 0.5 → 0.6.** Piece 2 changes the format (a new
entry kind, a new export document), so the bump is earned, not
ceremonial. The anchor format does NOT change: the checkpoint
body keeps exactly its eight keys — no key id is added to the
signed body (the strongest continuity property available, and
the brief's conditional TS-verifier obligation is met the other
way: verification semantics DO change, via the key schedule, so
the TS verifier is updated anyway). Checkpoints issued under
0.5 remain valid: §15.1 now states a verifier accepts `spec`
`jacquard/0.5` or `jacquard/0.6` in a checkpoint body. New log
entries carry `jacquard/0.6`; the golden vectors regenerate.
The cross-drill fixtures are committed evidence of the 0.5
drill and are NOT regenerated — they record what ran under
0.5; the drill itself is re-run as a suite check, not re-filed
as evidence. (If the drill disagrees under 0.6 that is a spec
bug by the standing rule; watch for it at the test pass.)

**Piece 1 — keys.** §15.3 rewritten to the built design:
(a) keys are PKCS#8-encrypted at rest (cryptography's
best-available encryption); the passphrase arrives via the
`JACQUARD_ANCHOR_PASSPHRASE` environment variable or a tty
prompt — never argv, never logged; signing verbs unlock per
run. `keygen`/`rotate` refuse to write an unencrypted key; a
pre-0.6 unencrypted key still loads (migration must be able to
anchor) but is exactly what rotation replaces. (b) Rotation
continuity without touching the signed body: the witness repo
gains `keys.json`, a registry whose per-`log_id` `signs_from` /
`signs_until` windows partition each log's checkpoint sequence;
the envelope `pubkey` must equal the scheduled key, so the
registry cannot rewrite history — it can only describe it, and
the `prev_checkpoint` hash chain (key-agnostic) links across
the boundary. The verifier learns the schedule from `--pubkey`,
from `--rotation-seq` + `--rotated-pubkey` (kept), or from the
registry via `--keys` (new). (c) The rotation is executed on
the REAL setup: successor key generated under an interim
passphrase held only in a mode-0600 file outside any repo
(coordinator batches the owner's re-wrap), checkpoint seq 2 at
length 507 signed by the successor, both keys + windows in the
witness repo, README rotation note, `pubkey.txt` advanced to
the successor. Cold verification from fresh clones of both
public repos closes the piece.

**Piece 2 — sealing (§16, new).** Design reviewed before
implementation by a hosted model panel of one (DeepInfra
DeepSeek-V4.1-Flash, one hostile-review pass over the format;
material use logged here per the brief). Four of its attacks
changed the design: (1) "no selective omission" was circular
for cherry-picked exports → exports are PREFIX-ONLY, so an
omitted seal entry breaks seq/prev/head like any omission;
(2) the seal set is committed twice — in the log and as
`seal_set_hash` in the export header, recomputed by the
verifier; (3) unanchored-tail seals are a real weakness →
verification reports `seals_anchored` explicitly, and the live
run additionally produces a demonstration checkpoint covering
the seal entry so the fully-anchored case is exercised, not
just described; (4) the soundness claim is stated precisely —
binding comes from linkage + anchor heads, the marker check is
consistency, sealed entries authenticate transitively. Two
critique points were answered rather than adopted: class stays
in the marker because the brief REQUIRES the export to name
sealed classes (the metadata tradeoff is stated in §16.4, not
hidden); and commitments come in two modes — `hash`
(publicly checkable, hides nothing at low entropy — §16.4 says
so in those words) and `keyed` (HMAC under an operator-held
redaction key; unkeyed verifiers get consistency, keyed
verifiers with the original get correctness). A seal names
history only (target seq < seal seq), never a `seal` entry,
and field paths resolve inside the target's body only, so
structural fields are unsealable by construction. The fold
ignores `seal` entries exactly as it ignores `import` entries;
the state hash is untouched.

Live-run shape (acceptance): the frozen proof log cannot grow
seals (it is frozen), so the run builds a working log = the 507
proof entries + one appended seal entry sealing the
operator-identity fields the log actually carries
(`released_by` ×26, `rejected_by` ×1 — `decided_by` in this log
names rules, not people, and is not sealed). The redacted
export verifies against the public anchors
(`verified_to_anchor`, anchored 507, tail 1 — the tail IS the
seal entry, stated not spun) and fully (`verified`, tail 0)
against the demonstration checkpoint at 508. The unredacted
working log and the frozen original both still verify. A
tampered sealed field fails, in tests and in the run record.

**Piece 3 — compliance mapping.** `docs/compliance-mapping.md`:
the BUILT mechanisms mapped to SOC 2 CC6/CC7 and ISO 27001
A.8/A.12 control shapes, labelled as a mapping, not a
certification, with auditor-visible gaps named (key custody as
operated — one operator, one machine, no HSM; no SIEM; no
retention policy; no access review process). Written last,
against what pieces 1–2 actually shipped.


### Slice 21 — implementation, part 1: version 0.6 + key management (2026-11-02)

Shipped in this part: `SPEC_VERSION` → `jacquard/0.6` (seal
regen, vectors regenerated, conformance full-log fixture
regenerated — the replay corpus was NOT regenerated: it is a
historical 0.5 log, see the TS note below); `seal` added to the
entry kinds (fold ignores it, like `import`); checkpoint-body
validation accepts `jacquard/0.5` and `jacquard/0.6` per §15.1.

Key management, per the §15.3 design: `generate_key` requires a
passphrase (argument, else `JACQUARD_ANCHOR_PASSPHRASE`) and
writes PKCS#8 best-available-encryption, mode 0600;
`load_private_key` resolves the passphrase the same way for
encrypted files and still loads a pre-0.6 unencrypted key;
`key_is_encrypted` reports the at-rest state. The CLI prompts on
a tty when the variable is unset — never argv. Registry:
`load_key_registry` + `schedule_from_registry` (windows must
partition the sequence; gap/overlap refused by name).
`anchor_entries` takes `history_schedule`: existing history
authenticates under the schedule and the signing key must be
the scheduled key for the new sequence — a retired key
anchoring past its boundary is a tool refusal, tested. New CLI
verb `rotate`: loads the old key, generates the encrypted
successor, and writes `keys.json` with per-log `signs_until` /
`signs_from` derived from the checkpoints actually published.
`verify` gains `--keys`. Existing anchor tests were adapted to
the new keygen contract (fixture supplies the passphrase via
the environment channel; assertions unchanged).

Two findings worth the record. (1) The registry file broke the
checkpoint scan: `load_checkpoints` walks `*.json` and reported
`keys.json: not a checkpoint envelope` on the first post-rotate
anchor. The registry is a transport file, not an envelope —
both loaders (Python and TS) now skip it by name. (2) The TS
chain verifier required every entry's `spec` to equal the
CURRENT version, which the 0.6 bump exposed against the frozen
0.5 replay corpus (check e). The Python reference performs no
such check — the hash recompute binds the exact spec value —
so the TS reading was the divergence: `verifyChain` now
requires a `jacquard/` spec string and lets the recompute do
the binding. This is the slice-19 pattern (a TS-side reading
corrected against the reference), not a spec change.

State after part 1: Python **294 passed, 7 skipped** (285
baseline + 9 new key-management tests); TS checker **13 PASS,
0 SKIP, 0 FAIL**. Remaining in this slice: the rotation on the
real anchors setup, §16 sealing (implementation + live run),
and the compliance mapping.

### Slice 21 — implementation, part 2: rotation on the real setup + sealing (2026-11-02)

**Rotation, executed on the live anchors setup.** An interim
passphrase was generated on the Oracle into
`~/.jacquard/PHASE8-INTERIM-PASSPHRASE.txt` (mode 0600, outside
any repo; the value appears in no commit, log, or report — the
coordinator batches the owner's re-wrap from that path).
`jqanchor rotate` generated the successor
(`ce805efd…48845f5072`) encrypted under it and wrote
`keys.json` into the witness repo: retired key
`1aa240ac…b3072be5` with `signs_until` = seq 1 for the
proof-run log, successor `signs_from` = seq 2. The retired key
file was re-wrapped encrypted under the same interim
passphrase (it was unencrypted — the pre-0.6 state §15.3 now
describes as migration debt) and the successor installed at the
default key path, also encrypted; both files mode 0600.
Witness repo, two commits, pushed and ls-remote-verified:
`df7f705` (registry + `pubkey.txt` advanced + README rotation
note) then `34f1c24` (checkpoint seq 2, length 507, spec
`jacquard/0.6`, `prev_checkpoint` chaining to seq 1's body
hash). Verification, Python and TS identical: registry
schedule → `verified`, 3 checkpoints, 507/507, tail 0; old key
alone → failed at seq 2; successor alone → failed at seq 0;
explicit `--rotation-seq 2` flags → verified; the forged log
against the registry → failed at checkpoint 0 with
`internal_chain_ok` true.

**Sealing.** `src/jacquard/sealing.py` + `tools/jqseal.py`
implement §16 as designed: `seal` appends a seal entry to a
COPY (the source is never modified), `export` writes the
prefix-only redacted document, `verify` runs the §16.3
procedure and reports the §15.5 vocabulary plus
`seals_applied` / `seals_anchored` / `commitments_checked`.
Twelve new tests: roundtrip, unanchored-seal reporting, prefix
slices with `checkpoints_beyond`, five tamper shapes (sealed
marker, seal entry, unsealed field, clear-text leak, omitted
entry — all detected, stage named), the wrong-value seal that
passes consistency and fails against the original, keyed-mode
dictionary resistance, the refusal set, and the proof-log
twin of the live run. One test caught its own author: the
"value is gone" assertion tripped on the CLASS name
`operator-identity` containing the substring — the value is
sealed, the class is disclosed by design; the assertion now
checks the value fragment exactly.

**Live run** (record: `docs/slice21/README.md`, export +
demonstration checkpoint committed there): working log = the
frozen 507 + seal entries at 507/508 sealing the 27
operator-identity fields the log carries (26 `released_by` +
1 `rejected_by`). Export vs the public anchors:
`verified_to_anchor`, anchored 507, tail 2 — the tail IS the
seal entries, and `seals_anchored` honestly reads false;
against a scratch store adding a successor-signed checkpoint
at 509: `verified`, tail 0, `seals_anchored` true,
`commitments_checked` full. Frozen original: still `verified`
507/507. Tampered marker: `failed`, stage `seals`, entry 23
named. The public anchors history was NOT extended to 509 —
deliberately: the frozen log's cold verification against the
public repo must stay exactly `verified` 507/507, and a
checkpoint beyond 507 would make the frozen log read as
truncated under §15.5. The 509 checkpoint is committed here as
evidence instead.

State after part 2: Python **306 passed, 7 skipped**; TS
checker **13 PASS, 0 SKIP, 0 FAIL** (re-run at the close).
Remaining: the compliance mapping, README/CHANGELOG close,
cold-clone verification.

### Slice 21 — close (2026-11-02)

All three pieces against their acceptance, with evidence:

1. **Key management.** Spec §15.3 rewritten before the code
   existed and now describes exactly what shipped. The live
   key is encrypted at rest (successor at the default path,
   successor-signed checkpoint 2 in the public witness repo);
   the retired key is re-wrapped encrypted; the interim
   passphrase lives only at `~/.jacquard/PHASE8-INTERIM-
   PASSPHRASE.txt` (mode 0600, outside any repo) for the
   coordinator's batched owner re-wrap. Rotation continuity:
   checkpoints 0–1 verify under the retired key's window, 2
   under the successor's, the registry schedule verifies the
   frozen log 507/507 in Python and TS, and each key alone
   fails at the boundary (seq 2 / seq 0 respectively).
2. **Sealing.** §16 as designed (critique-informed, deviations
   reasoned in the design entry). Tests: 12, including five
   tamper shapes and the proof-log twin. Live run:
   `docs/slice21/` — export `verified_to_anchor` against the
   public anchors (tail = the seal entries, `seals_anchored`
   false, stated), `verified` with commitments `full` against
   the demonstration checkpoint at 509, frozen original still
   `verified`, tamper detected at stage `seals`.
3. **Compliance mapping.** `docs/compliance-mapping.md` —
   access control, change management, audit logging and key
   management mapped to SOC 2 CC6/CC7/CC8 and ISO 27001 A.8
   shapes, labelled a mapping not a certification, with eight
   auditor gaps named, the interim-passphrase custody state
   among them.

Deviations from the brief, all recorded above where they
happened: the checkpoint body was NOT amended (registry +
hash chain carry continuity instead — the brief's conditional
TS obligation was met anyway, since verification semantics
changed); the public anchors history was not extended past
507 (the frozen log's cold verification must stay
`verified`, and §15.5 reads a longer history as truncation
evidence against it — the 509 checkpoint is evidence in this
repo instead); the conformance full-log fixture regenerated
at 0.6 while the historical replay corpus did not (TS chain
verifier relaxed to the Python reference's semantics, a
reading correction, not a spec change); the Phase 7
cross-drill fixtures stand as the 0.5 drill's evidence and
were not re-filed.

Final state: spec **0.6**; Python **306 passed, 7 skipped**;
TS **13 PASS, 0 SKIP, 0 FAIL**; cold-clone verification from
fresh clones of both public repos recorded in the addendum
that follows this entry, per the standing pattern. Casey's
remaining item from this slice is the one already batched by
the coordinator: re-wrap the anchor keys with his own
passphrase and delete the interim file.

### Slice 21 — cold-verification addendum (2026-11-02)

Run after the close commit, from fresh clones of both public
repos on the Oracle (the jacquard clone at the post-rebase
main, which also carries slice 20's part 1 — the suites below
ran on that merged tree):

- `git clone SuperInstance/jacquard` → `python3 -m pytest -q`:
  **306 passed, 7 skipped**.
- Same clone, `conformance/ts`: `node check.ts` → **13 PASS,
  0 SKIP, 0 FAIL**.
- Frozen proof log vs a fresh clone of
  `SuperInstance/jacquard-anchors`, registry schedule
  (`--keys`): Python `verified`, anchored 507, tail 0,
  3 checkpoints; TS `verify-anchor.ts --keys` identical.
- The slice 21 export from the cold clone alone: vs the public
  history `verified_to_anchor` (507 anchored, tail 2, 27 seals,
  `seals_anchored` false); with the committed demonstration
  checkpoint placed at `checkpoints/<log_id>/000003.json`,
  `verified` (509, tail 0, `seals_anchored` true) — the cold
  verifier needed nothing beyond the two public repos and the
  spec.
- Secret scan of the slice range (512085f..close): zero PEM
  private-key headers in `git log -p`; no key or passphrase
  file tracked; the private keys remain mode 0600 under
  `~/.jacquard/` on the Oracle and nowhere else.
# Phase 8 — slice 20: the Rust kernel port (2026-11-02)

## Slice 20 — design, recorded with the slice's first commit (2026-11-02)

Third implementation of the kernel contract, chartered by the
Phase 8 brief: port to Rust in a new in-repo `rust/` tree,
mirroring the TS conformance layout; the full golden-vector
suite with zero SKIPs; the cross-drill extended to three
kernels; §12.1 signatures identical on both real corpora;
crate metadata publish-ready with the crates.io name checked
and nothing published. Spec read-only for this slice (slice
21 owns spec edits this phase); divergences are recorded,
never silently aligned.

Decisions, with reasons:

- **Port the port.** The Rust tree mirrors `conformance/ts/`
  module for module — `core.rs` for `jacquard.ts`, `kernel.rs`
  for `kernel.ts`, with senses / signature / anchor split out
  of the latter — and the method is slice 19's: a deliberate
  port of the reference behaviour, checked against the Python
  where the TS is ambiguous. Two proven readings beat one
  fresh reading of the prose.
- **Scope = the TS port's scope.** A kernel without the
  lifecycle machines installed (§10.4 defines that as 0.1
  behaviour): §§1–5, 7 (+7.1), 11.2–11.3, 12.1, 15.5. The
  machine profile, WFQ scheduler, booking profile, learner
  beyond §12.1 and bundles stay fold-covered / out of scope,
  and a `machine` envelope gets the same scope-naming SPEC
  refusal the TS port gives (language name changed).
- **Own canonical code; three crates only.** The brief
  permits sha2 / ed25519-dalek / serde_json but requires any
  canonical serialisation to be own code, byte-exact. The
  port goes further: no JSON library anywhere — values are a
  custom insertion-ordered type (Python dict order matters to
  `py_repr` in refusal details and to object iteration in the
  fold and the wait pump) with an own parser (exact integers;
  Python's duplicate-key rule) and an own serialiser. Crates:
  `sha2`, `ed25519-dalek`, `flate2` (the last only so the
  checker can read the `.gz` fixtures). Integers are i64
  internally; the serialiser refuses outside ±(2^53−1),
  mirroring the TS reading (TS GAPS #2 stays honestly open).
- **Python semantics are a surface, not an accident.** The
  refusal `detail` strings embed Python `repr()` of lists and
  strings, Python truthiness, `True == 1` equality, and floor
  division — the cross-drill compares verdicts byte-for-byte,
  so `py_repr` / `py_eq` / `py_truthy` / `py_compare` and
  `div_euclid` / `rem_euclid` are ported as first-class
  helpers, exactly as kernel.ts did.
- **Rust is installed user-level on the build box** (rustup,
  minimal profile, stable — cargo 1.99.1 there at install
  time), never system-wide.
- **Crate name checked before metadata was written** (the
  brief's order): `jacquard` on crates.io is TAKEN — an AT
  Protocol client library (created 2025-10-04, 25 versions,
  latest 0.12.2, checked via the crates.io API from the build
  box). `jacquard-kernel`, `jacquard-rs` and
  `superinstance-jacquard` were all free at the same check;
  the package takes `jacquard-kernel` (library crate
  `jacquard_kernel`), version 0.5.0 aligned with the release
  line. The repository carries no licence, so none is
  claimed; `publish = false` stays until slice 23's batched
  owner steps clear the name/licence decisions. Nothing is
  published by this slice.
- **One divergence was already visible before the first
  build** and is recorded under Implementation below rather
  than discovered mid-port: spec §1's string-escaping prose
  contradicts the vectors and both existing implementations.
  The port follows the vectors (raw UTF-8), as the brief
  itself states the rule.

## Slice 20 — implementation (2026-11-02)

The port landed in one pass per module (`value` → `core` →
`senses` / `signature` / `anchor` → `kernel` → the three
binaries), and the evidence came back clean on the first
complete runs — recorded as it happened:

- **Checker: 13 PASS, 0 SKIP, 0 FAIL, exit 0** on the first
  full run — seal, vector chain (the non-ASCII checkpoint
  name `café-☃` included), checkpoint fold, envelope id, the
  3,295-entry replay log (hashes + fold), the 25-entry
  all-kinds full log, dictionary stored forms, sequencer
  end-to-end state (live and refolded), all 5 sense cases
  (method strings byte-identical), the anchor checkpoint
  (signature verifies, fails over a tampered body, §15.5
  reports verified 4/4 tail 0), §12.1 signatures over both
  proof-run corpora (8 + 27 queued decisions, item lists and
  their canonical hashes equal to Python's), and the §§4–5
  token-form battery.
- **Cross-drill: three identical hashes on the first run.**
  The extended orchestrator drives the 38-op stream through
  Python, TS and Rust: 52 entries, log sha256 `0cde737c…`
  in all three, verdict sha256 `021bce65…` in all three —
  the same hashes slice 19 committed for two kernels, now
  reproduced by a third. `cross_drill.py` builds the Rust
  binary itself; `rust.jsonl` / `rust-verdicts.json` are
  committed beside the existing artifacts.
- **Anchor CLI against the public anchors repo** (pubkey from
  the anchors clone): true proof-run-2 log `verified`
  507/507 tail 0 (exit 0); the forged fixture `failed` at
  checkpoint 0 with `internal_chain_ok: true` (exit 1); a
  257-entry prefix under a checkpoint-0-only history
  `verified_to_anchor` 250/257 (exit 0); a 300-entry
  truncation `failed` naming checkpoint 1 (exit 1); the
  Phase 5 log `unanchored` (exit 3). Every outcome and
  failure field matches the Python tool and the TS twin.
- **The §1 divergence, stated precisely** (also in
  `rust/GAPS.md` item 1): §1's prose prescribes the ASCII
  `\uXXXX` escaping form for all non-ASCII, but vector entry
  3's recorded hash recomputes only under raw UTF-8 — the
  reading the Python reference (`ensure_ascii=False`), the
  TS port (GAPS #3, closed in slice 19 on exactly this
  evidence) and the Phase 8 brief all carry. Expected per
  prose vs actual per vectors is a one-fixture discrimination
  (`vectors.json` entries[3]). The port follows the vectors;
  the spec was NOT edited; the prose correction is slice
  21's, as this phase's discipline assigns spec edits there.
- Compile hygiene: the release build finished with zero
  warnings on the final tree; `Cargo.lock` is committed so
  the drill's build is reproducible.

## Slice 20 — close (2026-11-02)

Acceptance, per item, with evidence:

1. **Full golden-vector suite in Rust, zero SKIPs** —
   `jacquard-check`: 13 PASS / 0 SKIP / 0 FAIL, exit 0,
   reproduced from the pushed tree on the build box (see the
   verification addendum pattern of prior slices; the numbers
   above are from the final tree).
2. **Three-kernel cross-drill** — 38 ops → 52 entries; logs
   byte-identical across Python / TS / Rust (sha256
   `0cde737cc8235d7b621ef454fc7738d6907d6ad1d7484f0068d376c87b4d6261`);
   verdicts byte-identical (sha256
   `021bce65f811d8c78a45ebbe8ec42964cf03b0080f4213946ade5491de668333`);
   evidence committed in `conformance/ts/cross-drill/EVIDENCE.txt`.
3. **§12.1 signatures identical on both real corpora** —
   checker item h: proof-run 8 queued decisions, items hash
   `eea8d627…` == Python; proof-run-2 27 queued decisions,
   items hash `176375f0…` == Python.
4. **Crate metadata publish-ready** — `rust/Cargo.toml`:
   name `jacquard-kernel` (the unqualified `jacquard` is
   taken on crates.io — AT Protocol client, latest 0.12.2,
   API-checked 2026-11-02; `jacquard-kernel` free at the
   same check), version 0.5.0, description / repository /
   keywords / categories set, `Cargo.lock` committed.
   Outstanding for slice 23's batched owner steps, stated
   plainly: no licence exists in the repo to claim, and
   `publish = false` stays set until then. Nothing was
   published.
5. **No Python/TS regressions** — the slice touches no
   Python or TS source except the drill orchestrator
   (extended, still byte-comparing the original two outputs);
   the Python suite and the TS checker were re-run from the
   final tree at close (numbers in the coordinator's report).

Spec divergences found: exactly one — the §1 string-escaping
prose (item above + `rust/GAPS.md` #1), recorded for slice
21 and not edited. Port-scope and inherited-gap notes are in
`rust/GAPS.md` (items 2–4): the machine-envelope scope
refusal mirrors the TS port's recorded boundary, and TS
GAPS items 1, 2, 5, 15 remain open for the same stated
reason — no discriminating fixture exists — with the Rust
readings matching the TS ones.

### Slice 20 — addendum: the anchors rotation (2026-11-02)

Recorded at close, because it changes what the anchor
evidence above refers to: while this slice ran, slice 21
rotated the operator anchor key on the public anchors repo
(its charter — key management is beachhead 2's remainder).
Checkpoint 2 for the proof-run-2 log is signed under a
successor key with checkpoint-body spec `jacquard/0.6`, and
a `keys.json` registry records the windows (retired key
signs seq 0–1; successor from seq 2). The anchor outcomes in
the implementation entry above were reproduced on the build
box against the published **0.5 history (checkpoints 0–1)**,
before and independently of that rotation, and match the
v0.5.0 Python tool and the TS twin exactly. The Rust
verifier is a spec 0.5 verifier and refuses the 0.6
checkpoint at history authentication — the correct 0.5
behaviour; 0.6-aware verification is slice 21's
deliverable. Full note: `rust/GAPS.md` item 5.

### Slice 20 — alignment to spec 0.6 (2026-11-02, after slice 21 landed)

Slice 21 landed while this port was in flight (its close
rebased cleanly onto slice 20's part 1, 88d5222), and the
coordinator directed slice 20 to treat spec 0.6 as its port
target on the merged tree. What the alignment changed in
`rust/`:

- Version constants and seal to `jacquard/0.6`; crate
  version to 0.6.0, aligned with the release line.
- The `seal` entry kind (section 16): accepted by the log
  layer, NO fold effect. The golden vectors do not exercise
  the kind (the regenerated full-log fixture carries none),
  so the port owes it acceptance only — a crate unit test
  (`seal_kind_round_trips_and_is_inert`) proves the
  canonical round-trip and the inert fold; jqseal-equivalent
  tooling is export-layer work, out of scope, and was not
  built.
- Chain verification relaxed to the reference's semantics,
  matching the TS fix: an entry's `spec` must be a
  `jacquard/` string and the hash recompute binds its exact
  value — the historical 0.5 replay corpus (3,295 entries)
  still verifies end to end under the 0.6 kernel.
- Anchor verification is registry-aware: checkpoint bodies
  naming spec `jacquard/0.5` or `jacquard/0.6` are both
  accepted (section 15.1 (0.6)), and
  `jacquard-verify-anchor --keys <registry>` builds the
  pinned schedule from the `keys.json` windows for the
  presented log's id, as the TS twin does. Checkpoint body
  unchanged: exactly the same 8 keys; no key id added.
- The cross-drill orchestrator now falls back to
  `~/.cargo/bin/cargo` when cargo is not on PATH (it failed
  once on exactly that, on this box).

Evidence on the merged tree (main 0b99a9e + this slice):
Rust checker **13 PASS, 0 SKIP, 0 FAIL** (new 0.6 values:
seal 0d639ec0…, envelope id f2f036a0…, vector fold
403bea8c…); crate unit test 1 passed; three-kernel drill
exit 0 — log sha256
411bb3e7e6853744ffa74501781275353dd1bda42a6936302a35e6845bf409bb
and verdicts sha256
25746e6f2dbaef202acd8c5121ccdc17822e25064f89c5f79fe64d0c97e126a7,
identical in Python, TS and Rust; section 12.1 signatures
unchanged and identical on both corpora (eea8d627… /
176375f0…). Anchor battery against the live anchors repo
(34f1c24): `--keys` verifies the frozen proof-run-2 log
507/507 (3 checkpoints, exit 0); retired key alone fails
at checkpoint 2, successor key alone at checkpoint 0
("envelope pubkey is not the pinned key for its
sequence"); the forged fixture under `--keys` fails at
checkpoint 0 with `internal_chain_ok: true` — the Python
tool's registry run agrees (verified, 507). Python suite
306 passed, 7 skipped; TS checker 13 PASS, 0 SKIP,
0 FAIL. The section 1 escaping divergence (GAPS item 1)
survives into spec 0.6 unchanged — still recorded, still
not edited by this slice.


### Slice 22 — gpu-queue live (beachhead 3): opening (2026-11-02)

Builder: the slice-22 lane, working in its own Oracle clone
(`~/jacquard-gpu`, from main@0b99a9e). Thor booking:
`jacquard-build` row on the agent-inbox schedule board
(2026-11-03 01:15 UTC, ~3h, check-by 05:00 UTC).

**Terrain re-verified before relying on it (read-only):**
`gpuq status` from the Thor's door: queue empty, feeder OFF,
1,637 jobs done lifetime, 0 failed; state in
`~/gpu-queue/{queue.json,events.jsonl,status.json}`. The
daemon's successor rule (read in `daemon.py`, not assumed):
a finite job dispatches only when another job is queued
behind it or the feeder is on — so the live chain below
always carries a named successor, and the window's last job
is a declared sentinel that stays queued in gpuq (the feeder
stays OFF; nothing will dispatch the sentinel, and the report
says so).

**Thor route — verified, with a finding.** The brief offers
two routes and asks which works to be recorded. From this
operator VM, `ssh -F ~/workspace/ssh/thor.config thor` works
end-to-end (ProxyJump via the Oracle to the Thor's reverse
tunnel slot 2225; the operator VM's key is authorised on the
Thor). From the Oracle itself, direct SSH to the tunnel slot
(127.0.0.1:2225) was tried with every key the Oracle holds —
all denied: no Oracle key is authorised on the Thor, and
adding one would be a persistent Thor-side change the slice's
constraints forbid. So: repo work, the live log's canonical
home, anchoring and verification live on the Oracle; bridge
invocations execute on the operator VM (the host holding the
authorised key), each one a fresh process, and after every
invocation the log + journal are copied to their canonical
Oracle path with sha256 equality checked and recorded here.
The bridge transport is a configurable command prefix
(`JACQUARD_GPU_THOR_CMD`, defaulting to the thor.config
door) precisely so this is configuration, not code.

**Bounded start — stated BEFORE the first live dispatch**
(and published into the live kernel log as its policy
record, a `gpu-policy-record` sense entry at genesis):

- Governed namespace: the gpuq lane **`jacquard`**.
- Job class: **`gpu-bench`** — short, finite GPU
  bench/inference jobs submitted through the bridge, each
  declaring one output artifact under
  `~/jacquard-gpu-live/` on the Thor. Chosen because a small
  torch matmul bench in the Thor's `~/ml/.venv` (verified
  present: torch 2.11.0, CUDA available) genuinely runs in
  well under a minute and produces a real, consumable result
  file; the ComfyUI route was not needed and no service was
  started or touched.
- Policy (`gpu-bridge-policy/1`, data in
  `adapters/gpu_queue.py`, applied through the kernel's rule
  hook so decisions are real kernel decision entries):
  ALLOW — known producer (`jacquard-build`, `operator`),
  governed class, no denied/held shape (policy/1 allows the
  plain dispatch). HOLD — network-fetch shapes (curl/wget
  without execution) and unknown producers queue for a
  batched hash-bound operator decision via `tools/jq.py`; a
  held job dispatches only after a release entry exists.
  DENY — feeder shapes (any command invoking `gpuq feeder`)
  and fetch-and-execute shapes (fetch piped to a shell, or a
  shell `-c` body containing a fetch) are denied by shape,
  reason recorded in a `gpu-policy` sense entry.
- Live kernel log: NEW log, own genesis, own log_id, at
  `/home/ubuntu/jacquard-gpu-live/kernel.jsonl` on the
  Oracle (canonical home; see the route note above).
- Live window: **7 governed submissions** (2 plain benches,
  1 held-then-released bench, 2 denied shapes, 1 consuming
  bench, 1 sentinel successor), inside the booked window
  2026-11-03 01:15–05:00 UTC.
- Anchoring: the live log joins the anchoring cadence —
  anchored at window open and window close into
  SuperInstance/jacquard-anchors under its own log_id,
  successor signer, passphrase via environment only.

**Thor-side actions taken so far: none beyond read-only**
`gpuq status` / `gpuq list`, reading `gpuq`/`daemon.py`/
`queue.json`/`status.json`, and a torch availability probe
(`~/ml/.venv/bin/python -c 'import torch...'` — a read-only
import + `cuda.is_available()`, no job submitted). Zero new
persistent processes or services; nothing installed.

Code chunk 1 (this commit): `adapters/gpu_queue.py` (the
bridge: policy as data + rule hook, journal-before-add
dispatch with adopt-by-name crash recovery, poll outcomes,
downstream-use sense, counts), `tools/jqgpu.py` (per-
invocation CLI: init/submit/dispatch/poll/senses/counts),
`tests/test_gpu_queue_bridge.py` (8 tests against an
in-memory FakeThor: policy record first, exactly-once
dispatch, adoption, two-sided denial, hold-until-release,
poll + downstream-use both ways, failure reporting).

### Slice 22 — live run and close (2026-11-02)

The live window ran 2026-11-03 01:37–01:42 UTC inside the
booking. Anchored at open before any submission (anchors
`bbc41c6`, checkpoint seq 0 at length 8, successor signer),
then, in order: bench-1 allowed → gpuq job-3; bench-2
allowed → job-4 (its queueing released bench-1 under the
successor rule); feeder-shaped submission DENIED
(`feeder-shape`) and fetch-and-execute DENIED — neither in
`gpuq list`, feeder verified still OFF afterwards; held-1
from unknown producer `mystery-lane` HELD in the kernel
queue (binding `9a77f702…06b38`, absent from gpuq),
released hash-bound via `tools/jq.py`, then dispatched →
job-5; bench-3 allowed with declared use of bench-1's
artifact → job-6, its output file embedding bench-1's exact
sum (25602.857421875); sentinel v1 DENIED — a bridge false
positive (prose mentioning gpuq + feeder matched the shape;
see the report's disagreement classification), shape
tightened in part 2, sentinel v2 allowed → job-7, still
queued in gpuq at close as the declared successor end-state.
Poll wrote all four completions into the log (confirm +
`gpu-outcome` entries); senses published (`queue-depth`,
two `output-use`, `gpu-downstream-use`: 1 of 4 completed
outputs used, ratio 2500 bp). Dispatch was invoked after
every step and once more at the end: 5 jacquard jobs in
gpuq, exactly one per allowed action — no re-adds.
Anchored at close (anchors `4b339e9`, seq 1 at length 91);
verification `--pubkey ce805efd…f5072`: **verified 91/91,
tail 0**. The `--keys` registry route cannot schedule a
post-rotation log_id (partition error, exact text in the
report) — recorded as a policy/tooling gap, not forced.

Final counts (log-derived): submitted 8, allowed 4, held 1
(→released→dispatched), denied 3, dispatched 5, completed
4, failed 0. Full evidence and the complete Thor-action
list: `docs/slice22-live-report.md`; live log + journal
committed under `docs/slice22/`, canonical log on the
Oracle at `~/jacquard-gpu-live/kernel.jsonl` (sha256
`a0fa08c7…`, identical to the committed copy).

Thor-side actions (complete): read-only probes listed in
the opening entry; five `gpuq add` calls via the bridge
(job-3…job-7); artifacts created by the jobs themselves
under `~/jacquard-gpu-live/` (bench-1/2, held-1, bench-3;
no sentinel.json — it never ran). Feeder never invoked, no
services touched, nothing installed, zero new persistent
processes. The Thor booking row is marked DONE in the
follow-up agent-inbox commit.

### Slice 23 — packaging and the 1.0 release (Phase 8, coordinator-run)

Opening entry, written before the work. Scope per the Phase 8
brief: package the finished thing for the curated shelf and
tag **v1.0.0** only when the release-readiness checklist
passes with evidence. Ground facts established first:

- Registry names: `jacquard` is taken on PyPI (a University
  of Michigan bioinformatics tool), on npm (a reserved-name
  package), and on crates.io (an AT Protocol library).
  `jacquard-kernel` is free on all three (PyPI 404, npm 404,
  crates.io per slice 20) — one qualified name across every
  registry; the Python import package stays `jacquard`.
- Licence: the repo carried none. The fleet norm is MIT
  (pincher, cocapn, signal-chain, exoj all carry LICENSE
  files; pincher's is MIT, © SuperInstance). Slice 23 adds
  MIT for SuperInstance and claims it in all three package
  metadata files.
- Spec §1 erratum: the string-escaping prose (ASCII-safe
  form) contradicts the vectors and all three implementations
  (raw UTF-8) — recorded as a divergence by slice 20 and
  carried unchanged into 0.6. The seal derives from the spec
  version string (`sha256("jacquard-spec/0.6")`), not the
  spec text, so the prose correction moves no hash: it
  lands in this slice as spec 0.6 erratum 1, prose only.
- Slice 22's recorded blocker — `verify --keys` cannot
  schedule a log_id absent from the witness registry (both
  keys default from seq 0, windows collide) — is treated
  as an operator-procedure gap, not a licence to guess: the
  registry gains the live gpu log's true window (successor
  key from seq 0) as a published statement in the witness
  repo, the procedure is documented, and a `register-window`
  verb is named as future work in the not-built list.

### Slice 23 — work record (2026-11-03)

- **Spec erratum** landed (part 1, 110227b): §1's escaping
  paragraph now states the raw-UTF-8 rule, with the erratum
  note in the text. Verified no-hash impact by construction
  (seal = `sha256("jacquard-spec/0.6")`) and by suite: 314
  passed on the edited tree before the commit.
- **Licence**: MIT, © 2026 SuperInstance (fleet norm —
  pincher's file is the template), claimed in pyproject,
  Cargo.toml and the new conformance/ts/package.json.
- **Packaging** (part 2, 6a356e6 + builds): distribution
  renamed to `jacquard-kernel`, versions aligned at 1.0.0.
  `python -m build` produced sdist + wheel; the wheel was
  installed into a fresh venv and, run from /tmp against the
  site-packages copy only, verified `SPEC_SEAL` against
  spec/vectors and canonical hashing (SMOKE OK). `cargo
  package --allow-dirty` produced `jacquard-kernel-1.0.0.crate`
  (52,693 B; the packaged tree compiles). `npm pack
  --dry-run` produced the `jacquard-kernel-1.0.0.tgz` shape
  (6 files, 39.7 kB). Nothing published; `publish = false`
  stays in Cargo.toml for the owner steps.
- **Registry defect — analysis, not assumption.** The
  coordinator first "fixed" slice 22's blocker by publishing
  the gpu log's window (successor from seq 0) into the
  witness `keys.json` (anchors badd09d after repair, below).
  Cold verification then STILL raised the partition error,
  which forced the actual read of `schedule_from_registry`
  (src/jacquard/anchor.py:408): every registered key
  contributes an interval for every log_id, defaulting
  `signs_from` to 0 when unlisted, and an empty window is
  inexpressible (until < from is malformed). So no registry
  content can schedule a post-rotation log under the 0.6
  grammar — slice 22's blocker is a grammar defect, not an
  operator-procedure gap. Disposition for 1.0.0: the true
  window stays published as a statement of fact; the
  limitation is stated in the anchors README (rewritten
  accordingly), this repo's README not-built list, and the
  release checklist; the gpu live log verifies 91/91 from
  cold clones via the explicit successor-key form
  (`--pubkey ce805efd…`, reproduced this slice). The null-
  window grammar fix is named owed work.
- **Process incidents (coordinator's own, recorded)**: two
  heredoc appends through the SSH wrapper lost their quoting
  in transport and executed backtick fragments as shell
  commands. The first (spec bullet + this log's opening
  entry) was caught before any commit and redone via
  base64 transfer. The second reached the anchors repo
  README as a mangled fragment inside commit 972fba6; it
  was caught on read-back, removed in 1a48bfe, and the
  section was later rewritten whole (badd09d is the
  correction commit for the procedure text). No content
  was lost in either case; every repair was verified by
  reading the file back. Lesson restated: base64 for any
  non-trivial text through this transport, always.
- **Checklist + tag**: `docs/release-readiness-1.0.md`
  carries the itemised evidence and the batched owner
  steps (anchor passphrase re-wrap; PyPI pending publisher
  or token; crates.io token + publish flag; npm token; the
  shelf listing). Tag follows the checklist's pre-tag
  items; the from-the-tag verification is recorded in the
  post-tag addendum entry.

### Slice 23 — post-tag verification addendum (v1.0.0)

Tag **v1.0.0** = commit e068a13 (annotated tag 691bdef),
pushed and ls-remote-verified. All verification below ran
from a **fresh clone of the tag** (`/tmp/jq-tag`), not the
working tree:

- Python suite: **314 passed, 7 skipped**.
- TypeScript checker: **13 PASS, 0 FAIL**.
- Rust checker (built from the tag): **13 PASS, 0 FAIL,
  0 SKIP**.
- Three-kernel cross-drill from the tag: logs and verdicts
  **byte-identical** (all three).
- Anchoring, tag clone against a fresh clone of the public
  witness repo: proof-run-2 **verified 507/507, tail 0**
  under the key registry; the gpu-queue live log
  **verified 91/91, tail 0** via the explicit successor-key
  form; the forged fixture **failed at checkpoint 0**
  (stage: prefix) with `internal_chain_ok: true`, exit 1 —
  the designed outcome.
- **Cold-agent drill from the release README: PASS.** A
  fresh agent with only the tagged repo ran the README's
  operator drill end-to-end (seed → queue → hash-bound
  approve/deny → execute → replay), reproduced every
  predicted final state (approved closed, denied refused,
  dispatched closed-and-confirmed), and ran the suite at
  314 passed. Friction was very low: manual transcription
  of the 64-char ids/bindings (unambiguous, did not block)
  and one README paraphrase of the execute output that did
  not match the tool's single-line form verbatim — the
  paraphrase is corrected in the same commit as this
  addendum.

Phase 8 is complete: slices 20–23 all landed with their
documentation, and the phase's remaining owner actions are
the batched list in `docs/release-readiness-1.0.md`
(anchor-passphrase re-wrap; PyPI / crates.io / npm first
publishes; the shelf listing). The Oracle board booking for
this lane is marked DONE.

# Phase 9 — fix the defect, prove it on the real queue, pave the publish path (2026-11-03)

## Slice 24 — design, recorded before building (2026-11-03)

Phase 9 slice 24: the registry-grammar fix named as owed work
at v1.0.0. Coordinator-run in a fresh Oracle clone
(~/jacquard-p9, from main@f66b769); Oracle board row booked
(agent-inbox e1a3975).

**The defect, from the source** (`schedule_from_registry`,
src/jacquard/anchor.py): every registered key contributes a
window for every log_id; a log_id missing from `signs_from`
defaults to 0 and one missing from `signs_until` is
open-ended, so an empty window is inexpressible. The live
witness registry therefore cannot schedule the gpu-queue live
log (9cbf80c8…): the retired key names that log in neither
map, defaults to a full window from seq 0, and collides with
the successor's true window — the recorded error is "key
registry windows for log 9cbf80c8… do not partition its
checkpoint sequence (gap or overlap after seq None)". The log
was born after the rotation and is signed only by the
successor; the 0.6 grammar has no way to say so.

**The fix — null windows.** A log_id omitted from BOTH maps
of a key's entry means the key signs nothing for that log:
it contributes no interval to that log's schedule. A log_id
omitted from one side only keeps its 0.6 meaning (unbounded
on that side). All other rules unchanged: participating
windows must still partition the log's checkpoint sequence,
gaps and overlaps still refuse by name, and a schedule that
leaves seq 0 uncovered still refuses.

**Format version: the registry document bumps, the spec
takes an erratum.** The registry carries its own format
string; it becomes `jacquard/anchor-keys/2`. Verifiers accept
both: /1 documents are read under the legacy rule (every key
participates, defaults as in 0.6) and /2 documents under the
null-window rule — a document is never read by a grammar it
was not written under. Spec version: **0.6 erratum 2**, not
0.7, reasoning recorded here per the brief: no log-entry,
checkpoint, envelope, or seal byte changes; the kernel
SPEC_VERSION and seal are untouched (slice 23's erratum-1
precedent: the seal derives from the version string, and
nothing a seal covers moves); the registry is a transport
document whose own format version is exactly the seam slice
21 built for its evolution, and the /1→/2 bump is what makes
the grammar change honest — a /1 reader refuses a /2 registry
by name (the format check is exact-match), so the new reading
can never be silently applied by old tooling. The erratum
text in §15.3 states the grammar change openly, as erratum 1
stated its correction. The witness keys.json is republished
as /2 with its key entries byte-identical apart from the
format string — its content already states the /2 reading as
fact; the republish makes it schedulable.

**Safety.** Null windows cannot manufacture acceptance: the
§15.5 procedure still requires the envelope pubkey to equal
the scheduled key and the signature to verify, so a registry
claiming a key signed outside its true window fails at the
envelope binding, naming the checkpoint seq ("envelope pubkey
is not the pinned key for its sequence"); a registry that
drops a key whose checkpoints exist leaves those sequences
covered by another key's window (binding failure again) or
uncovered (partition refusal). The registry remains a
description that verification checks, never a source of trust.

**Vectors + twins.** New `anchor_registry` section in
spec/vectors/vectors.json: schedule cases (/2 null window,
/2 rotation partition, /1 legacy reading pinned, overlap
refusal, gap refusal, uncovered-seq-0 refusal) and
authentication cases (a window claim outside the truth fails
with the named detail). Python implements first
(anchor.py + tools/jqanchor.py unchanged at the CLI surface),
then the TS twin (conformance/ts/verify-anchor.ts + check.ts)
and the Rust twin (rust/src/anchor.rs + its checker), each
running the same section.

**Acceptance (pinned by the brief).** (1) The REAL gpu live
log verifies via the registry path — not explicit-key — in
all three implementations (91/91 over checkpoints seq 0/1);
(2) the pre-rotation proof log still verifies 507/507 via
the registry in all three; (3) a registry scheduling a key
outside its true window fails by name (vectors + tests);
(4) all suites green; (5) ship as v1.0.1 — version strings,
CHANGELOG, release-readiness addendum, tag verified from a
cold clone of the tag; (6) both READMEs' limitation
statements updated as a doc event (this repo's not-built
list loses the registry-grammar item; the anchors README's
limitation section is rewritten to record the fix).
