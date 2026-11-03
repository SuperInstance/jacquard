# Release readiness — v1.0.0 (2026-11-03)

The checklist the Phase 8 brief requires before the v1.0.0
tag. Every item passes with the evidence named, or the tag
does not happen. Verification "from the tag" means a fresh
clone of the tag artifact itself, not the working tree.

## Items

- [x] **Python suite green** — 314 passed, 7 skipped
  (314 passed, 7 skipped FROM THE TAG CLONE).
- [x] **TypeScript conformance green** — 13 PASS / 0 SKIP /
  0 FAIL (13 PASS / 0 FAIL FROM THE TAG CLONE).
- [x] **Rust conformance green** — 13 PASS / 0 SKIP / 0 FAIL
  (13 PASS / 0 FAIL FROM THE TAG CLONE).
- [x] **Three-kernel cross-drill byte-identical** — one
  38-op stream through Python, TS and Rust: log sha256
  `411bb3e7…` and verdicts sha256 `25746e6f…` identical in
  all three (`conformance/ts/cross-drill/EVIDENCE.txt`;
  re-run from the tag clone).
- [x] **Cold-agent drill from the release README** — a fresh
  agent with only the tagged repo reproduces the operator
  drill (PASS from the tag clone: a fresh agent ran the
  README operator drill end-to-end, all predicted final
  states reproduced; see the builder's log addendum).
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

## Addendum — v1.0.1 (2026-11-03, Phase 9 slice 24)

v1.0.1 is a one-defect release: the registry-grammar fix
recorded in this checklist for 1.0.0 ("the key-registry
grammar makes a registry unable to schedule a log born after
a rotation") is **fixed and the limitation is retired**.
Spec 0.6 erratum 2: registry format `jacquard/anchor-keys/2`
adds null windows (a `log_id` omitted from both of a key's
maps = that key signs nothing for that log); /1 documents
keep the legacy reading; verifiers accept both, each under
its own grammar. No checkpoint, entry or seal byte changed.

Evidence (all from the v1.0.1 tree): Python suite 318 passed
+ 7 skipped; TypeScript and Rust checkers 14 PASS / 0 SKIP /
0 FAIL (new `anchor_registry` vector section: 9 schedule
cases, 2 authentication cases). The gpu-queue live log
verifies via the registry path — not explicit-key — in all
three implementations (91/91, checkpoints seq 0/1), and the
pre-rotation proof log verifies 507/507 under the same
registry; a forged-window registry fails by name at
checkpoint 0. The witness registry
(SuperInstance/jacquard-anchors @ d1fa84c) stands republished
as /2 with entries byte-identical apart from the format
string, and its README's limitation section rewritten.

The batched owner steps above carry forward unchanged, with
**1.0.1** as the version to publish wherever they say 1.0.0;
docs/PUBLISHING.md (Phase 9 slice 26) supersedes them with
exact strings and paved workflows.
