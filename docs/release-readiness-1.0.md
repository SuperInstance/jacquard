# Release readiness — v1.0.0 (2026-11-03)

The checklist the Phase 8 brief requires before the v1.0.0
tag. Every item passes with the evidence named, or the tag
does not happen. Verification "from the tag" means a fresh
clone of the tag artifact itself, not the working tree.

## Items

- [x] **Python suite green** — 314 passed, 7 skipped
  (release tree; re-run from the tag clone in the post-tag
  addendum).
- [x] **TypeScript conformance green** — 13 PASS / 0 SKIP /
  0 FAIL (release tree; re-run from the tag clone).
- [x] **Rust conformance green** — 13 PASS / 0 SKIP / 0 FAIL
  (release tree; re-run from the tag clone).
- [x] **Three-kernel cross-drill byte-identical** — one
  38-op stream through Python, TS and Rust: log sha256
  `411bb3e7…` and verdicts sha256 `25746e6f…` identical in
  all three (`conformance/ts/cross-drill/EVIDENCE.txt`;
  re-run from the tag clone).
- [x] **Cold-agent drill from the release README** — a fresh
  agent with only the tagged repo reproduces the operator
  drill (result recorded in the post-tag addendum).
- [x] **Anchoring drill green** — from cold clones of the
  two public repos: the proof-run-2 log verifies 507/507
  under the key registry in Python and TS; the forged
  fixture fails the anchor check at checkpoint 0; the
  gpu-queue live log verifies 91/91 via the explicit
  successor-key form (see the named limitation).
- [x] **CHANGELOG complete** — 1.0.0 section covers slices
  20–23 on top of the 0.6.0 (slice 21) record; derived from
  the builder's log, which remains the full record.
- [x] **README honest** — the built / not-built lists match
  the tree at the tag (slices 20–23 recorded; the not-built
  list names registry publication, the registry-grammar
  fix, the register-window verb, the TS/Rust port scope,
  and the quarantine driver).
- [x] **Licence present** — MIT (fleet norm), claimed in
  pyproject, `rust/Cargo.toml`, `conformance/ts/package.json`.
- [x] **Spec erratum landed** — 0.6 erratum 1 (§1 raw-UTF-8
  prose), prose only; seal and vectors unchanged.
- [x] **Package shapes build** — wheel + sdist built and
  the wheel smoke-tested in a fresh venv (seal + canonical
  hashing from site-packages); `cargo package` produces
  the crate; `npm pack` produces the tarball. Nothing was
  published.

## Named limitations that ship with 1.0.0 (not blockers, stated)

- The anchor registry grammar cannot yet express "this key
  does not sign this log": a log born after a rotation
  verifies via the explicit single-key/rotation flags, not
  `verify --keys`. Fix is owed work (null windows in
  `schedule_from_registry` + twins + a spec note).
- Anchor keys are passphrase-encrypted at rest, but the
  operating passphrase is currently an interim one held in a
  mode-0600 file on the Oracle (owner re-wrap pending —
  see owner steps).
- TS/Rust ports are kernels without the lifecycle machines
  installed (spec 10.4 scope), as recorded in their GAPS.

## Batched owner steps (Casey's hands; the phase does not stall on them)

1. **Anchor passphrase** — read the interim passphrase from
   `~/.jacquard/PHASE8-INTERIM-PASSPHRASE.txt` on the Oracle,
   re-wrap BOTH anchor keys with a passphrase of your own
   (the anchor tooling's keygen/rewrap path with
   `JACQUARD_ANCHOR_PASSPHRASE` set per run), then delete
   the interim file. Until then, at-rest protection is only
   as strong as that file's permissions.
2. **PyPI** — create/confirm the PyPI account and add a
   pending publisher (GitHub OIDC: owner `SuperInstance`,
   repo `jacquard`, workflow of your choice) or an API token
   for the project name **`jacquard-kernel`**; then the
   first publish is `python -m build && twine upload dist/*`
   from a release clone (sdist + wheel already build clean).
3. **crates.io** — confirm the crates.io account, create an
   API token, remove `publish = false` in `rust/Cargo.toml`,
   then `cargo publish` in `rust/` (the crate tree already
   packages and compiles as `jacquard-kernel 1.0.0`).
4. **npm** — confirm the npm account (or create the
   `@superinstance` org if a scoped name is preferred over
   the unscoped `jacquard-kernel`, which was free at check
   time), create a granular access token, then
   `npm publish` in `conformance/ts/` (tarball already
   packs: 6 files, ~40 kB).
5. **Shelf listing** — with 1–4 done as desired, list
   `jacquard-kernel` 1.0.0 on the curated shelf (si-ready)
   per its usual intake; the release tag and this checklist
   are the intake evidence.
