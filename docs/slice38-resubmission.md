# Slice 38 — resubmission semantics (spec 0.7, §3.1)

Phase 14, slice 38. Charter: BUILD-BRIEF-PHASE14.md. This
slice settles what a duplicate envelope means in the kernel
contract, implements it in all three kernels, and audits
the live deployments' logs for duplicates that already
landed.

## The finding this answers

Spec §3 always promised that an envelope's `id` is an
idempotency key — "resubmitting the same envelope returns
the original verdict and appends nothing". The promise was
kept only inside one process: the verdict cache was
per-process state. Phase 13's `jq submit` build found the
consequences, all of them cross-process shapes:

- an **allowed** duplicate was re-decided and **silently
  re-executed**;
- a **queued** duplicate appended a second decision entry,
  then **crashed** on machine-instance creation (the
  approval instance already existed);
- a **refused** duplicate appended a **second refusal**.

The shipped adapters are cross-process submitters by
construction (the ZCode hook is a fresh process per tool
call), so these were production shapes held back only by
the adapters' own journal bookkeeping. Phase 13's verb
papered over them with a folded-record scan of its own —
the workaround whose limits §3.1 records.

## The decision (SPEC §3.1, written before the code)

**Recorded-verdict replay.** Once a submission's decision
is recorded in the log, resubmission — in the same process
or any later one — returns the recorded verdict with
`"duplicate": true` added, and never re-decides, never
re-executes, never appends. The sequencer rebuilds its
verdict cache from the log at construction: the first
submission decision per proposal id (operator
release/reject/expire entries are not submission
decisions; wait-pump records never precede the submission
decision), and, for definitions and machines, the
acceptance entry — which from 0.7 carries the envelope
hash in an `envelope` body field so it can be found.

Rejected alternatives, recorded in the spec note:

- **Current-disposition replay** (report the *latest*
  decision entry — what Phase 13's verb improvised at the
  surface): one question receives different answers at
  different times, and it crashes on shapes its outcome
  map lacks (expired items). The recorded verdict is the
  answer to "what did the kernel decide when this was
  submitted"; current disposition is read from the record,
  not from a resubmission.
- **Refusing duplicates** (REFUSED(DUPLICATE)): duplicate
  delivery is the normal at-least-once shape of
  cross-process adapters; a refusal pushes idempotency
  into every adapter and invites retry storms.

Two boundary rulings, also in §3.1:

- **Later operator decisions do not change the recorded
  verdict.** A released-then-resubmitted proposal hears
  "queue" (its submission verdict), marked as a replay;
  nothing re-executes.
- **Pre-recording refusals stay unrecorded.** Envelope,
  request-shape and wait-spec refusals append nothing, so
  there is nothing to replay; resubmission re-derives the
  same refusal deterministically. One refusal moved across
  the line: the **define-check refusal now records a
  fault decision entry** exactly as UNDERDECLARED always
  did (before 0.7 it recorded nothing but lifecycle steps
  and could append extra transition entries on
  resubmission). Section 3's older sentence "every refusal
  is itself recorded" was scoped to match — it was prose
  ahead of the implementation for pre-decision refusals.

One consequence is stated in the spec rather than hidden:
the acceptance entry's envelope hash makes the folded
dictionary/machine sections commit to the submitting
envelope, so a log's state hash is a fact about that log's
own submission history. State hashes were already
history-dependent (versions carry entry sequence numbers);
no rule equates two logs' state hashes. The vector
replays in all three checkers were aligned to the
generator's envelopes, field for field, for this reason.

## Implementation

Python (`src/jacquard/sequencer.py`), TypeScript
(`conformance/ts/kernel.ts`) and Rust
(`rust/src/kernel.rs`) mirror each other:

- the verdict cache is initialised from
  `_recorded_verdicts()` / `recordedVerdicts()` /
  `recorded_verdicts()` over the folded log's entries;
- a cache hit returns a copy of the verdict with
  `"duplicate": true`;
- definition (and, in Python, machine) acceptance entries
  carry the `envelope` hash — the TS and Rust ports refuse
  machine envelopes by their standing §10.4 scope, fresh
  or replayed alike, and do not scan machine entries;
- the define-check refusal path appends the fault
  decision entry before returning.
- `tools/jq.py`'s `jq submit` now delegates to the kernel
  rule; its Phase 13 folded-record scan is deleted.

Spec 0.7 also bumps the seal (`jacquard-spec/0.7`); the
anchor tooling's accepted checkpoint versions gain
`jacquard/0.7` alongside 0.5/0.6. Historical logs fold
unchanged (the replay-log conformance fixture is
untouched and still verifies).

## Evidence

- **Python battery** `tests/test_resubmission.py` — 12
  tests, every one resubmitting through a *fresh*
  Sequencer over the same entries: duplicate allowed
  (exactly one execution), duplicate queued with
  lifecycles installed (the 0.6 crash shape; still
  decidable, executes once on release), duplicate denied,
  duplicate UNDERDECLARED (one fault), duplicate across a
  checkpoint, duplicate after release (hears "queue",
  executes nothing), duplicate after expire (the old
  verb's crash shape), duplicate definition, duplicate
  machine, define-check duplicate (one fault entry), an
  adapter-path duplicate through
  `coding_agent.submit_tool_action` (the ZCode hook's
  submission helper, same idem, two fresh sequencers),
  and in-process marking. Two pre-existing tests were
  updated to the 0.7 contract with the reason cited in
  comments (stronger assertions, none weakened). Full
  suite from the working tree: **359 passed + 7 skipped**
  (347 + the 12 new).
- **Conformance**: vectors regenerated; TS checker
  **14 PASS / 0 SKIP / 0 FAIL**; Rust checker
  **14 PASS / 0 SKIP / 0 FAIL**.
- **Cross-language drill**: a new `restart` op (fresh
  sequencer over the same entries) in all three drivers,
  and `fixture-resubmission.json` — 26 ops covering
  duplicate-allowed, duplicate-queued, duplicate-denied,
  duplicate-refused, duplicate across a checkpoint,
  resubmission after an operator release, duplicate
  definition, and an adapter-shaped dispatch proposal.
  Result (`EVIDENCE.txt`): **26 ops → 11 log entries**,
  logs byte-identical (sha256 `487a4995…`) and verdict
  streams byte-identical (sha256 `fa3a8881…`) across all
  three kernels. The original 38-op fixture is likewise
  byte-identical under 0.7 (log sha256 `b87f1fda…`).

## The live-log duplicate audit

`audit_duplicates.py` (this directory; read-only) groups
each log's decision entries by proposal id, counting
submission decisions under §3.1's definition (operator
decisions and wait-pump records excluded, counted
separately), and executions per proposal id. The auditor
was validated against a planted log first: it flags the
planted duplicate decision and duplicate execution and
correctly excludes the operator release and the wait-pump
record.

Findings, 2026-11-04:

| log | entries | proposals | dup decisions | executions | dup executions |
|---|---|---|---|---|---|
| gpu-queue live (Oracle) | 227 | 19 | **0** | 14 | **0** |
| booking board live (Oracle) | 260 | 23 | **0** | 23 | **0** |
| Orin seat live (pulled from the Orin) | 117 | 10 | **0** | 10 | **0** |
| proof run 1 (frozen) | 126 | 9 | **0** | 8 | **0** |
| proof run 2 (frozen) | 507 | 36 | **0** | 35 | **0** |
| gpu window 1 (docs/slice22) | 91 | 8 | **0** | 5 | **0** |
| booking board (committed copy) | 197 | 17 | **0** | 17 | **0** |

**No duplicate ever landed.** Across 1,525 audited
entries and 122 proposals, no proposal carries two
submission decisions and no proposal executed twice. The
kernel-level hole was real — Phase 13 demonstrated all
three failure shapes in a scratch log — but the
deployments' adapters deduplicated at their own surfaces
(the hook's journal scan, the bridge's single-flight
dispatch), so production history contains no instance.
History is noted, not rewritten: no log was modified by
this audit.

**ProArt seat log: not audited — the box is dark.** The
ProArt was unreachable on both routes during this slice
(direct tunnel route reset at the proxy; the Thor hub
port 192.168.0.78:2206 refused), the same state recorded
at Phase 11's stranger test. No committed copy of its
109-entry seat log exists (the device matrix records its
sha256 only). The audit covers every reachable
deployment; the ProArt row is an open item for whenever
the box returns, and the 0.7 kernel makes the question
moot for any log written from now on.
