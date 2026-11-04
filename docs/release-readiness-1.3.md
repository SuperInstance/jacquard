# Release readiness — 1.3.0

Tag `v1.3.0` (annotated; commit `a178d22`). Spec 0.7.
Phase 14 — settle the open questions: resubmission
semantics (slice 38), the MCode adapter (slice 39), the
clean-harness discovery test (slice 40). Per-slice
records: `docs/slice38-resubmission.md`,
`docs/slice39-mcode-live-fire.md`,
`docs/slice40-clean-harness.md`; the narrative record is
`docs/BUILDERS-LOG.md` (Phase 14).

## Verified from the tag (cold clone, this date)

- Python suite: **370 passed, 7 skipped**.
- TypeScript conformance: **14 PASS, 0 SKIP, 0 FAIL**.
- Rust conformance: **14 PASS, 0 SKIP, 0 FAIL**.
- Cross-language drill, both fixtures, byte-identical
  logs and verdict streams across all three kernels:
  the 38-op stream (log sha256 `b87f1fda…`) and the
  resubmission fixture — 26 ops → 11 entries (log sha256
  `487a4995…`, verdicts sha256 `fa3a8881…`). The clone's
  regenerated `EVIDENCE.txt` matches main's exactly.

## What the release is

- Spec 0.7 §3.1: resubmission returns the recorded
  verdict, marked as a duplicate, in every process —
  Phase 13's three cross-process failure shapes
  (silent re-execution, queue crash, double refusal)
  are impossible at kernel level in all three
  implementations, with a 12-case Python battery and
  the drill fixture as the standing evidence.
- The MCode adapter, live-fired and deployed on a real
  seat before it was claimed (slice 39's counts are from
  the deployment's kernel log, not from test fixtures).
- Slice 40's discovery negative is a result, not a gap
  in the release: it measures the distribution problem
  (registries, search), not the product.

## Known limitations (consolidated in the README)

Unchanged from 1.2.x except as noted: registry
publication pending (the operator's steps in
`docs/PUBLISHING.md` — now a twice-measured adoption
blocker); laptop profile not yet available; bubblewrap
does not hold on tegra kernels; TS/Rust ports are
§10.4-scope; no learner quarantine driver; the
consumption gate is delivered ready and inactive; no
TLS; no per-user identity; no trusted clock; the
standing rank-tie disposition. New in this release:
**MCode's plugin-hook host fails open** (slice 39), and
the Orin MCode 0.6.12 seat has not been live-fired (its
login had lapsed; re-fire awaits re-login). The ProArt
seat log's duplicate audit remains open — the box is
dark — and is moot for logs written under spec 0.7.

## Publication state

Nothing published to any registry. Package versions in
the three trees are 1.3.0. Publish workflows remain
dispatch-only; see `docs/PUBLISHING.md`.
