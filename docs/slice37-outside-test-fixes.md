# Slice 37 — fix what the outside found, re-test once (2026-11-03)

Slice 36's findings, classified, and what was done about
each. The rule for this slice: fix what is cheap and true
(docs and packaging first; product changes only when a
finding is load-bearing and the fix is small); anything
larger is reported, not built.

## Findings and dispositions

**F1 — Product gap (load-bearing, small): no generic
submit path in the operator CLI.** Run 4's agent — the
exact user of the batched-approvals starter — found
`tools/jq.py` exposes only {seed-demo, queue, status,
decide, execute, replay}: the flow the starter describes
could not be driven end-to-end for a user's own items.
**Fixed.** `jq submit <proposal.json>` (or `-` for stdin)
takes a proposal document ({producer, id,
declared_effects, body{requests}}), installs the standard
lifecycles on a fresh log (as seed-demo does), submits,
and prints the kernel's verdict as JSON; exit 1 on a
refusal. Battery: `tests/test_jq_submit.py`, 7 tests,
including the full submit → queue → hash-bound decide →
execution → replay path. Suite: 347 passed, 7 skipped
(was 340 + 7).

Building the verb exposed a kernel behaviour worth
recording precisely: **the kernel's verdict cache is
per-process** (`Sequencer._verdicts`), so a fresh-process
resubmission of an identical envelope was not idempotent
— a queued proposal's duplicate appended a second
decision entry and then raised an unhandled `Refusal`
from machine-instance creation; an allowed proposal's
duplicate was silently re-decided and re-executed; a
refused proposal's duplicate appended a second refusal
entry. In-process submitters (the service) and the
existing adapters (which keep their own journals) never
saw this; a CLI, whose whole life is fresh processes,
would have shipped it. The verb therefore carries
cross-process idempotency itself: it consults the folded
record, and for an already-decided envelope prints the
recorded verdict (the latest decision entry) with
`"duplicate": true` and changes nothing. All three
duplicate shapes are pinned by tests. **The kernel-level
question — what resubmission should mean once the
operator has since decided the item — is a design
decision for a future spec pass and is recorded here,
not settled by this fix.**

**F2 — Onboarding friction: the shipped surface never
demonstrated class-based auto-allow.** Run 4 concluded
the policy "cannot express" a routine class that sends
without queuing. True of the shipped surface; the kernel
expresses auto-allow two ways (effects outside the
protected set decide on submission; standing rules
compiled from the operator's own approvals auto-decide
repeated protected shapes) — but no doc showed either,
and the starter implied a submission path that did not
exist. **Fixed in docs.** The solo starter now shows the
real submission (a worked `jq submit` example) and states
the queueing model plainly: protected effects
(`send`/`notify`/`spend`/`irreversible`) queue for every
non-operator producer, there is no exemption class to
declare, and a routine class earns auto-decision by
repetition through standing rules — queue-first, then
earned trust. `docs/QUICKSTART.md` gains a "Submit your
own proposal" section; the README's drill gains the same
submission block. Before the docs were committed, the
coordinator ran the documented flow verbatim on a fresh
log (submit → queue → hash-bound approve → replay ends
`closed`) — the starter's promise is true as written.

**F3 — Fit-signalling: the docs claimed the uses without
the scale boundary.** Runs 1 and 4, independently, on two
different strong-fit profiles, reached the same flip
condition (multi-producer / multi-process / standing
rules) and hand-rolled at small scale. **Fixed in docs.**
The README's Known limitations gains the boundary in
plain terms ("Small, single-process work does not need
it…"), and both affected starters (batched approvals,
job-queue governance) gain the same honesty in their
Limits sections, each in its own terms.

**F4 — Packaging: registry absence bit live.** Both
strong-fit agents hit it (a failed `pip install`; a
failed `pip show`). Already known and already stated in
the docs: publication is prepared and waits on the
owner's registry steps (`docs/PUBLISHING.md`). Not
fixable from this phase; no action. (Run 4 also noted
PyPI's bare `jacquard` is an unrelated package — the
qualified name `jacquard-kernel` is already used
everywhere it matters.)

**F5 — Discoverability on this harness: not measurable.**
Recorded in the slice 36 report's method caveat; no fix
exists inside this phase. The re-test below inherits the
same limit.

**F6 — Positioning boundary (partial fit): recorded, not
chased.** Run 2's provenance-shaped need routed to
attestation tooling; Jacquard's verifiable-record story
is told in decision vocabulary. Non-adoption was the
correct outcome there; pitching the kernel at citation
ledgers would overfit the docs to a strained fit. No
change.

## The re-test

One fresh mid-work agent ran the affected profile (Run
4's batched-approvals task, pristine fixtures, identical
brief). **Primary task: PASS, exact** — sent set,
classes, outcomes and reject handling all match the
fixture's expectations a second time, with the
non-blocking property again proven in a decisions-absent
run.

**Surface re-test: inconclusive as run, stated plainly.**
This agent never visited the changed surfaces: its notes
record that Jacquard "exists in this workspace" — it
evaluated from background context and a `pip show` check,
never cloned the repo, never opened the starter, never
tried `jq submit`. Run 4's two walls were therefore
neither re-hit nor cleared by an outside user. What the
run does establish: the rejection rationale has narrowed
to the two reasons this phase did not set out to change —
registry absence (the owner's step) and the honest scale
boundary (now stated in the docs themselves) — and the
product's pattern was again adopted where its dependency
was not, in the agent's words: *"the genuinely borrowed
thing is Jacquard's batching discipline as a design
pattern, not a dependency"*, with the flip conditions
named a third time (multiple producers, tamper-evident
"why was this allowed" records, long operator absence).
The fixes stand on their own verification: the verb's
battery, and the coordinator's verbatim run of the new
docs' flow. No second re-test agent was spawned: repeating
the run until an agent adopts would manufacture the
result this phase exists to be able to hear "no" about.

## Release

v1.2.2: the `jq submit` verb (+7 tests), the doc fixes
above, this report, the CHANGELOG entry and
`docs/release-readiness-1.2.2.md`. Package versions
(pyproject / Cargo / TS package) remain 1.1.0, following
the 1.2.x practice — the git tag carries the release
version; the change is to the operator CLI (not the
packaged kernel) and the docs.
