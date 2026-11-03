# Release readiness — v1.2.1 (documentation release)

v1.2.1 is a docs-only release over v1.2.0. It changes the
voice and placement of the user-facing documentation and
nothing else.

## What changed

- `README.md` — rewritten as a production product's front
  door: definition and audience, the five governed uses,
  how it works, install (from git, stated plainly), the
  operator drill, the network service and its auth story,
  queue notifications, the ZCode adapter, chain-head
  anchoring, key management and sealed exports, a support
  matrix, known limitations, the repository layout, and a
  short Development & history pointer. The phase-by-phase
  build diary that previously formed the bulk of the file
  now lives where it belongs: `docs/BUILDERS-LOG.md`,
  `CHANGELOG.md`, `docs/PROGRAMME.md` and the slice
  reports — complete and untouched in substance.
- `docs/DEVICES.md` — retitled "Support & compatibility":
  a support-state table up front, deployment evidence
  summarised as support state, full records linked.
- `docs/QUICKSTART.md`, `starters/README.md` and the four
  starter kits — build attributions replaced with
  production statements; every number and record link
  preserved.
- `CHANGELOG.md` — the 1.2.1 entry.
- This addendum and the Phase 12 builder's-log entry.

## Invariants, checked

- **No fact changed meaning.** Every verified claim in the
  prior docs survives with its truth intact; limitations
  are stated more plainly (a dedicated Known limitations
  section in the README: registry publication pending,
  the laptop profile not yet available, the tegra
  bubblewrap platform limitation, the partial TS/Rust
  port scope, the learner's missing quarantine driver,
  the inactive consumption gate, no TLS / no per-user
  identity, no trusted clock, low-entropy hash
  commitments, no MCode adapter, the standing tie
  disposition, the open spec ambiguities).
- **Nothing was deleted.** `git diff v1.2.0..v1.2.1`
  touches only Markdown files; the build record is
  complete and stays in the repo.
- **No code changed.** No `.py`, `.ts`, `.rs`, `.toml`,
  `.json` or lockfile differs from v1.2.0 (a Cargo.lock
  touched by a local checker run was restored before
  commit; build litter was removed, not committed).

## Verification

- Suites re-run in the release clone (not merely carried):
  Python **340 passed, 7 skipped**; TypeScript conformance
  **14 PASS, 0 SKIP, 0 FAIL**; Rust conformance **14 PASS,
  0 SKIP, 0 FAIL** — identical to v1.2.0, as expected with
  no code change.
- Doc-currency pass: every document path referenced from
  the rewritten README, QUICKSTART, ONBOARDING, DEVICES
  and starters resolves against the tree (one apparent
  miss was the glob `tools/jq*.py`, a pattern, not a
  path).
- **Cold read:** one zero-shot agent read only the
  rewritten README and reported what the product is, what
  it does, how they would start, and what it does not do.
  Their account matched the verified record on every
  load-bearing point — including the full limitation set —
  so no corrective README edit was required.
