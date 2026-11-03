# Release readiness — v1.2.2 (outside-test release)

v1.2.2 ships what Phase 13's outside test found: one
small product fix (a missing CLI verb) and the doc fixes
that make the shipped surfaces tell the truth about
submission, queueing, and fit. The evidence chain is
`docs/slice36-outside-test.md` (the runs) and
`docs/slice37-outside-test-fixes.md` (findings, fixes,
re-test).

## What changed

- `tools/jq.py` — the `submit` verb: generic proposal
  submission for the operator CLI, with cross-process
  idempotency carried at the CLI layer (a duplicate
  prints the recorded verdict and changes nothing).
- `tests/test_jq_submit.py` — 7 tests: the full
  submit → queue → decide → execute → replay path,
  stdin submission, all three duplicate shapes
  (queued / allowed / refused), malformed input leaving
  no trace.
- Docs — README (submission block in the drill; the fit
  boundary in Known limitations), `docs/QUICKSTART.md`
  ("Submit your own proposal"), the solo starter (real
  submission example; the queueing model stated; a fit
  line in Limits), the job-queue starter (a fit line in
  Limits), `CHANGELOG.md`, this addendum, and the
  Phase 13 builder's-log entries.

## Invariants, checked

- **No fact changed meaning.** The docs' new claims were
  verified before commit: the documented submit flow was
  run verbatim on a fresh log (submit → queue →
  hash-bound approve → replay ends `closed`), and the
  queueing-model text matches `policy/1` and the learner
  mechanism as shipped.
- **The kernel is untouched.** No file under `src/`,
  `conformance/` or `rust/` differs from v1.2.1; the
  cross-process resubmission behaviour the verb guards
  against is recorded in the slice 37 report as a kernel
  design question for a future spec pass, not settled
  here.
- **Package versions unchanged** (pyproject / Cargo /
  TS package remain 1.1.0), following the 1.2.x practice:
  the git tag carries the release version, and the code
  change is to the operator CLI, which is not part of
  the packaged kernel.

## Verification

- Suites re-run in a fresh clone of the tag: Python
  **347 passed, 7 skipped** (340 + 7 at v1.2.1, plus the
  7 new submit tests; nothing weakened); TypeScript
  conformance **14 PASS, 0 SKIP, 0 FAIL**; Rust
  conformance **14 PASS, 0 SKIP, 0 FAIL**.
- **Re-test:** one fresh mid-work agent on the affected
  (batched-approvals) profile passed its primary task
  exactly; it did not visit the changed surfaces, so the
  surface re-test is recorded as inconclusive in the
  slice 37 report, with the reasons stated there.
