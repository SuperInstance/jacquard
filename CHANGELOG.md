# Changelog

Derived from `docs/BUILDERS-LOG.md`, which remains the full
record (decisions, reasons, dead ends).

## 1.1.0 — 2026-11-03

### Slice 27 — consumption policy v2 (Phase 10)
- Spec 0.6 **erratum 3**: new section 17, a deployment-
  policy note recording the consumption-pricing semantics
  the reference deployment implements. No kernel semantics
  change; no vector changes; the section 11.3
  downstream-use sense is unchanged.
- `adapters/consumption.py`: one pricing implementation
  shared by the shadow scorer and the bridge gate. The
  trailing use-ratio counts **completed consumption only**
  (a use counts when the consuming job's completion is
  recorded — never at declaration; a failed consumer
  counts for nothing), fixing the promise-flattery gap
  the Phase 9 shadow named in its own v1 semantics. The
  unbounded invisible cold-start exemption becomes an
  **exemption budget** denominated in completed outputs
  (reference 3), each exemption spent recorded as a claim
  in the accounting.
- Re-scored windows 1+2 (frozen log): would-holds 3 → 6,
  true positives 3 → 5, false positives 0 → 0, no-stake
  0 → 1 (sentinel-3, the named sentinel-marker residual);
  bench-7 repriced 6667 → 3333 bp and held (wasted-work
  true positive); 4 exemption claims, all in window 1.
  Findings: `docs/slice27-consumption-policy-v2.md`;
  scorer + rows: `docs/slice27/`.

### Slice 28 — the expensive class: inventory and gate
- Thor inventory from records (`docs/slice28/`): the
  gpu-queue's complete history holds 1,647 finished jobs,
  max 180.3 s, **zero ≥ ~5 GPU-minutes**; image studio
  and foundry portal records are seconds-scale on GPU.
  **No qualifying expensive class exists; the brief's
  honesty gate fired — no live window was run and none
  was manufactured.** The feeder class was shadow-scored
  at class level: 16,667 assets, 39 ever used (23 bp);
  ≈18.3 GPU-hours priced — validating the standing
  feeder-off ruling.
- The gate is built as machinery: a `consumption_gate`
  in a log's policy record (job class, threshold,
  exemption budget, optional `exempt_self_consuming`
  refinement) makes the bridge hold that class's
  submissions through the kernel's rule hook as
  `gpu-consumption-policy/2`, priced by
  `adapters/consumption.py`, accounted per item in
  `gpu-policy` sense entries. `jqgpu init
  --consumption-gate`, `jqgpu submit --class`. Battery:
  `tests/test_consumption_gate.py` (5 tests). **Not
  active on any live log.**
- Defect found in passing, fixed: declared uses rode
  only on the proposal body, which the rule hook never
  sees — the refinement was unpriceable live.
  `submit_job` now carries declared uses on the dispatch
  request as well (the body-level list remains the
  canonical record).

### Slice 29 — the note verb, v1.1 tidy
- `jqgpu note --event --text [--cause] [--job-log]`:
  the operator-note record window 2 improvised by hand
  (that log's seq 188) is now a verb —
  `GpuQueueBridge.operator_note` appends the
  `gpu-operator-note` sense entry in the same shape.
  Battery: `tests/test_jqgpu_note.py` (3 tests).
- README currency: the Phase 10 state above; a stale
  "Phase 8 (in progress)" line for slice 20 corrected.
- Suite at the tag: 332 passed, 7 skipped (was 318 + 7);
  TS/Rust conformance unchanged (the erratum is a
  deployment note; vectors untouched).

## 1.0.1 — 2026-11-03

### Slice 24 — the registry-grammar fix (Phase 9)
- Spec 0.6 **erratum 2**: the anchor key registry learns null
  windows. A registry document of format
  `jacquard/anchor-keys/2` reads a `log_id` omitted from BOTH
  of a key's maps as "this key signs nothing for that log";
  `/1` documents keep the legacy reading, and verifiers accept
  both, each under its own grammar. No checkpoint, entry or
  seal byte changes.
- The defect this fixes: at 1.0.0 no registry could schedule
  a log born after a key rotation (the gpu-queue live log),
  because an empty window was inexpressible; such logs
  verified only in explicit-key form. All three verifiers
  (Python, TypeScript, Rust) now verify that log via the
  registry path — 91/91 — and the pre-rotation proof log
  still verifies 507/507 under the same registry. A registry
  claiming a window outside the truth fails by name at the
  envelope binding.
- Conformance: new `anchor_registry` vector section (9
  schedule cases, 2 authentication cases) run by all three
  checkers — 14 PASS / 0 SKIP / 0 FAIL each; Python suite
  318 passed, 7 skipped, including real-log acceptance tests
  over vendored witness fixtures.
- The witness registry (SuperInstance/jacquard-anchors) is
  republished as /2, entries unchanged; both repositories'
  limitation statements updated.

## 1.0.0 — 2026-11-03

The 1.0 release: three implementations of one contract
(Python reference, TypeScript and Rust ports) at spec 0.6,
a live adapter surface (coding-agent hooks, network service,
gpu-queue governance), key-managed anchoring with a public
witness, sealed exports, and package shapes built for PyPI,
crates.io and npm under the qualified name `jacquard-kernel`
(registry publication itself waits on the batched owner
steps — see `docs/release-readiness-1.0.md`).

### Slice 23 — packaging and the 1.0 release (Phase 8)
- Spec 0.6 **erratum 1**: section 1's string-escaping prose
  corrected to the raw-UTF-8 form the golden vectors and all
  three implementations have always used. Prose only — the
  spec seal derives from the version string, so no canonical
  byte and no recorded hash changed. The divergence record
  stands in `rust/GAPS.md`.
- **MIT LICENSE** added (the repo carried none; MIT is the
  fleet norm) and claimed in all three package metadata
  files.
- Python distribution renamed `jacquard` → `jacquard-kernel`
  (the name `jacquard` is taken on PyPI, npm and crates.io);
  the import package stays `jacquard`. Version 1.0.0 across
  pyproject, `rust/Cargo.toml` and the new
  `conformance/ts/package.json`.
- Package evidence (local builds, nothing published): sdist
  + wheel built; the wheel installed into a fresh venv
  verifies the spec seal and canonical hashing standalone.
  `cargo package` produces `jacquard-kernel-1.0.0.crate`
  (compiles from the packaged tree). `npm pack` produces
  the `jacquard-kernel` tarball (6 files).
- Witness registry: the gpu-queue live log's true window
  (successor key from seq 0) published in
  `SuperInstance/jacquard-anchors`, and a defect named
  plainly — as built, the 0.6 registry grammar cannot
  schedule a log no registered key is listed for *not*
  signing (every key defaults to signing from seq 0), so
  post-rotation logs verify via the explicit single-key
  form until the grammar learns null windows. The gpu live
  log verifies 91/91 that way from cold clones; the
  limitation is stated in the anchors repo README and in
  the not-built list below in this repo's README.


### Slice 22 — gpu-queue live (Phase 8)
- `adapters/gpu_queue.py` + `tools/jqgpu.py`: the gpu-queue
  bridge — Jacquard governs real submissions to the Thor's
  GPU queue (lane `jacquard`, class `gpu-bench`) per dispatch
  over the existing SSH door, zero new Thor processes.
  Policy as data through the kernel's rule hook (feeder and
  fetch-and-execute shapes denied by shape; network-fetch
  and unknown producers held for hash-bound operator
  decision); journal-before-add dispatch with adopt-by-name
  crash recovery; poll-written outcomes; the downstream-use
  sense (C3 as a live reading). 8 FakeThor tests.
- Live run (report: `docs/slice22-live-report.md`, log +
  journal in `docs/slice22/`): 8 submitted, 4 allowed, 1
  held→released, 3 denied, 5 dispatched (gpuq job-3…job-7),
  4 completed; downstream-use 1 of 4 outputs used; the live
  log anchored at open and close under its own log_id
  (verified 91/91). One bridge false positive (sentinel v1)
  found live, fixed, and left standing in the log.

### Slice 20 — the Rust kernel port (Phase 8)
- `rust/`: the third implementation of the kernel contract,
  a port of the TS port mirroring its layout — `value`
  (canonical values, own JSON parser, the §1 serialiser),
  `core` (envelope, log, fold — the `jacquard.ts`
  equivalent), `kernel` (26 primitives, dictionary +
  evaluator, policy gate, sequencer + §7.1 wait pump),
  `senses` (§11.3), `signature` (§12.1), `anchor` (§15.5).
  Dependencies: `sha2`, `ed25519-dalek`, `flate2` only;
  canonical serialisation is the crate's own code.
- The Rust conformance checker (`jacquard-check`) runs the
  FULL golden-vector suite with **zero SKIPs**: 13 PASS —
  every section the TS checker runs, including the §12.1
  signature comparison over both proof-run corpora
  (8 + 27 queued decisions, item-for-item and by hash).
- Cross-language drill extended to three kernels: the same
  38-operation stream through Python, TS and Rust produces
  **byte-identical logs and byte-identical verdicts**;
  evidence (with the sha256s of the day) in
  `conformance/ts/cross-drill/EVIDENCE.txt`. At spec 0.6:
  log sha256 411bb3e7…, verdicts sha256 25746e6f…, all
  three kernels.
- `jacquard-verify-anchor`: the Rust twin of `jqanchor
  verify`, including the spec 0.6 registry form (`--keys`):
  against the live anchors repo it verifies the frozen
  proof-run-2 log **507/507 across slice 21's key rotation**
  (3 checkpoints), each single key failing at exactly its
  boundary (retired → checkpoint 2, successor → checkpoint
  0); the forgery fails at checkpoint 0 with
  `internal_chain_ok: true`; the 0.5-history outcomes from
  before the rotation (250/257 verified-to-anchor under a
  checkpoint-0-only history; truncation failed at
  checkpoint 1; Phase 5 log unanchored) stand as recorded
  in the builder's log.
- Spec divergence recorded in `rust/GAPS.md` (not edited —
  slice 21 owns spec edits): §1's string-escaping prose
  states the ASCII `\uXXXX` form, but the golden vectors and
  both prior implementations prove raw UTF-8; the port
  follows the vectors.
- Crate metadata publish-shaped: name checked on crates.io —
  **`jacquard` is taken** (AT Protocol client, latest
  0.12.2); the package carries the free qualified name
  `jacquard-kernel`, version 0.6.0 aligned with the release
  line (the port was built at spec 0.5 and aligned to 0.6
  when slice 21 landed it — see the builder's log). The
  repo carries no licence, so none is claimed;
  `publish = false` until slice 23's owner steps. Nothing
  was published.
- Spec 0.6 deltas ported: the `seal` entry kind (accepted,
  fold-inert — section 16; a crate unit test proves the
  round-trip; sealing tooling itself is export-layer and
  out of scope), the relaxed chain spec rule (the hash
  binds the entry's own `jacquard/` spec value, so the
  historical 0.5 replay corpus still verifies), checkpoint
  bodies naming 0.5 or 0.6, and the registry-aware
  verifier above.
- Evidence: Python suite at **306 passed, 7 skipped**; TS
  checker at **13 PASS, 0 SKIP, 0 FAIL**; Rust checker
  **13 PASS, 0 SKIP, 0 FAIL** — all from the merged tree.
## 0.6.0 — 2026-11-02 (Phase 8, slice 21 — beachhead 2 remainder)

Specification 0.6. Slice 23 will tag the release; this entry
records the slice.

### Key management (spec 15.3 rewritten)
- Anchor keys are passphrase-encrypted at rest (PKCS#8,
  best-available encryption), mode 0600, outside every repo;
  the passphrase is supplied per run via the
  `JACQUARD_ANCHOR_PASSPHRASE` environment variable or a tty
  prompt — never argv, never logged. `keygen` refuses to write
  an unencrypted key; a pre-0.6 unencrypted key still loads
  (migration), and rotation replaces it.
- Key registry `keys.json` (`jacquard/anchor-keys/1`) in the
  witness transport: per-log `signs_from` / `signs_until`
  windows must partition each log's checkpoint sequence;
  verifiers take the schedule from the registry (`--keys`), an
  explicit `--pubkey`, or `--rotation-seq` + `--rotated-pubkey`.
  New CLI verb `rotate`; the anchoring tool refuses to sign
  outside the signing key's scheduled window.
- Rotation executed on the real setup: retired key signed
  checkpoints 0–1; successor (passphrase-encrypted under an
  interim passphrase held only in a mode-0600 file on the
  Oracle, pending the owner's re-wrap) signed checkpoint 2 at
  length 507, `prev_checkpoint`-chained across the boundary.
  Registry schedule verifies 507/507 in Python and TypeScript;
  either key alone fails at the boundary.
- The checkpoint body is unchanged (still exactly eight keys);
  checkpoints issued under spec 0.5 remain valid — a 0.6
  verifier accepts `jacquard/0.5` and `jacquard/0.6` checkpoint
  bodies (spec 15.1).

### Sealed exports (new spec section 16)
- New entry kind `seal` (no fold effect): commits, in the log
  before export, to the redaction of designated body fields —
  (entry, field, class, mode, commitment), the commitment a
  domain-bound hash (`hash` mode) or an HMAC under an
  operator-held redaction key (`keyed` mode).
- Redacted exports (`jacquard/redacted-export/1`) are
  prefix-only views: sealed values are replaced by their
  commitments, the seal set is bound by a `seal_set_hash`, the
  anchored log is never altered, and verification reports the
  section 15.5 outcomes plus `seals_applied`,
  `seals_anchored` and `commitments_checked`. Tooling:
  `src/jacquard/sealing.py`, `tools/jqseal.py`.
- Live run over the real proof-run log (`docs/slice21/`): 27
  operator-identity fields sealed; the export verifies
  `verified_to_anchor` against the public anchors and
  `verified` against a demonstration checkpoint covering the
  seal entries; the frozen original still verifies; a flipped
  sealed marker fails at stage `seals`, entry named.

### Compliance mapping
- `docs/compliance-mapping.md`: built mechanisms mapped to
  SOC 2 CC6/CC7/CC8 and ISO 27001 A.8 control shapes —
  labelled a mapping, not a certification — with auditor
  gaps named (key custody as operated, no SIEM/monitoring,
  no retention policy, asserted-not-authenticated identity,
  single-operator duties).

### Conformance
- Python suite: **306 passed, 7 skipped** (285 baseline + 9
  key-management + 12 sealing tests; existing anchor tests
  adapted to the passphrase-required keygen, assertions
  unchanged). Golden vectors and the conformance full-log
  fixture regenerated at spec 0.6; the historical 0.5 replay
  corpus was NOT regenerated — the TS chain verifier now
  accepts earlier `jacquard/` entry specs, matching the Python
  reference (the hash recompute binds the exact value).
- TypeScript checker: **13 PASS, 0 SKIP, 0 FAIL**;
  `verify-anchor.ts` gained `--keys` registry support and
  reproduces the rotation outcomes exactly.


## 0.5.0 — 2026-11-02

Specification 0.5; Phase 7 — slice 18 (chain-head anchoring)
and slice 19 (the full TypeScript port), which completes the
phase. Tagged v0.5.0.

### Slice 19 — the full TypeScript port
- `conformance/ts/kernel.ts`: a deliberate port of the Python
  reference (the opposite method from slice 8's spec-only fold
  implementation, and recorded as such) — dictionary +
  evaluator (§§4–5: computed effects as the union over
  expansion, the form-agnostic walk, unknown dict forms
  REFUSED(SPEC) by name), sequencer + policy gate + decision
  queue + the §7.1 wait pump, sense computation (§11.3,
  contention and authority), the §12.1 shape signature, and
  the §15.5 anchor verifier (Ed25519 via Node's built-in
  crypto — no new dependency).
- The TS conformance checker now runs the FULL golden-vector
  suite with **zero SKIP lines**: 13 PASS, exit 0. Every
  former SKIP (`vectors.definitions`, `vectors.state`,
  `vectors.senses`, `vectors.anchor`) is a real check with
  comparisons at least as strict as the Python suite's for the
  same vectors, plus the §12.1 signature comparison over both
  proof-run corpora (8 + 27 queued decisions, item-for-item
  and by canonical hash, against a Python-generated fixture)
  and the stock-kernel half of the slice 17 token-form
  battery.
- Cross-language drill (`conformance/ts/cross-drill/`): one
  38-operation stream through both sequencers → 52 log
  entries, **byte-identical logs and byte-identical verdicts**
  (sha256 in the committed `EVIDENCE.txt`).
- `conformance/ts/verify-anchor.ts`: the TS twin of
  `jqanchor verify`; against the public anchors repo it
  reproduces the Python outcomes exactly (true log verified
  507/507; forgery failed at checkpoint 0 with
  `internal_chain_ok: true`; tail 250/257; truncation failed
  at checkpoint 1; Phase 5 log unanchored).
- GAPS.md: items 16, 17, 18 closed; items 3, 7, 10, 11, 14
  closed with the discriminating check named; item 13 closed
  in part; items 1, 2, 5, 15 remain open (no discriminating
  fixture exists); the TS port's §10 boundary recorded as
  port scope, not a spec gap.
- `docs/anchor-drill.md` corrections from the cold-verifier
  pass (the eighth output field `log_id` named; §4 starts
  from a clean scratch dir and echoes its exit code; the
  recursive `--checkpoints` search explained at the point of
  use; the drill's guided-not-blind limit stated).
- Evidence: Python suite unchanged at **285 passed,
  7 skipped**; no spec bug was found by the port — every
  divergence was a TS-side reading corrected against the
  reference (one, the fold's decision chain, is recorded in
  the builder's log).

### Added
- Chain-head anchoring (spec §15): signed Ed25519 checkpoints
  of (log length, head hash, spec version) published outside
  the kernel's store. A checkpoint body has exactly eight keys;
  what is signed is the body's canonical bytes; checkpoints for
  one log hash-chain via `prev_checkpoint`; a log is named by
  its genesis hash (`log_id`), with the stated limitation that
  identity names a lineage and the (length, head) pair does the
  binding. No signed timestamp: existence-at-a-time rests on
  the transport's publication record.
- Anchor tooling (`src/jacquard/anchor.py`,
  `tools/jqanchor.py`): `keygen` (operator key at
  `~/.jacquard/anchor-key.ed25519`, mode 0600, outside every
  repo, overwrite refused), `anchor`, `verify`. Verification
  reports VERIFIED / VERIFIED-TO-ANCHOR (anchored prefix and
  unanchored tail as distinct numbers) / UNANCHORED / FAILED
  naming the first divergent checkpoint — never a bare
  boolean. Anchoring is the tooling's only non-stdlib
  dependency (`cryptography`); the kernel stays
  zero-dependency.
- First transport: the separate public repo
  `SuperInstance/jacquard-anchors` (append-only discipline:
  one commit per checkpoint, adds only). The frozen Phase 6
  proof log is anchored there at lengths 250 and 507.
- Forged-log fixture (`tests/data/forged/`, generator +
  provenance): the proof log with seq 100's outcome flipped
  and the chain recomputed — fully self-consistent under §2,
  caught by §15 at checkpoint 0. Both directions asserted in
  `tests/test_anchor.py` (18 tests).
- Cold-verifier drill (`docs/anchor-drill.md`): exact steps
  and expected values for an independent verifier given only
  the public anchor repo, the spec and a presented log.
- Golden vectors gain an `anchor` section (§15): one
  checkpoint over the vector chain under a published test
  key. TS conformance: version aligned to 0.5, both fixtures
  regenerated, `vectors.anchor` declared SKIP (verifier work,
  not fold work; GAPS item 18) — 7 PASS, 4 SKIP.

### Evidence
- Suite at this entry: 285 passed, 7 skipped (266 + 18 anchor
  + 1 anchor vector). TS checker: 7 PASS, 4 SKIP.
- The true proof log verifies `verified` (507/507, tail 0)
  against a fresh clone of the anchor repo; the forged log
  fails at checkpoint 0 with `internal_chain_ok: true`.

## 0.4.0 — 2026-11-02

Specification 0.4; Phase 6 of the build, landing in two steps
(slice 16, then slice 17). The Phase 5 proof run's headline
deficit — approvals not compiling into standing rules — is
closed, and the Phase 4 completeness probes' recorded hazard
(the `any`-quotation C2 hole) is closed with it.

### Added
- Shape signatures (spec §12.1): a pure, log-derivable
  function of a queued decision's request list — a dispatch's
  command skeleton (shell `-c` unwrapped, segments split,
  programs by basename, flags by name, urls/paths/numbers
  abstracted), a write's file extension, a send's host —
  refining the mining shape so one coarse queued shape no
  longer lumps distinct commands together.
- Operator labels (spec §12.2): an operator's release or
  reject of a queued item, joined to the proposal it decided,
  is first-class training data. The wait pump's mechanical
  re-decisions carry no operator field and never label;
  expiry labels nothing.
- Two-pass mining and origin-relative scoring (spec
  §§12.3–12.4): candidates are mined from policy outcomes
  (origin "mined", as before) and from operator verdicts
  (origin "operator"); operator-origin rules climb the same
  eval → shadow → canary → active ladder, scored on operator
  verdicts alone — rule-made decisions never grade
  themselves, canary-era rejects block activation, and later
  operator rejects demote. Operator-origin rules fire only on
  an exact signature match inside the queued population.
- Token-form accounting (spec §§4–5): the token forms are
  enumerated; the effects walk descends into every token
  position except a literal's value; unknown dict forms are
  REFUSED(SPEC) with the form named; C2 is stated with the
  quotation case included (quotation defers evaluation,
  never accounting).

### Evidence
- Replay proof in the suite (tests/test_operator_learner.py)
  on the frozen Phase 5 proof log, and a live second proof
  run (docs/proof-run-2-2026-11-02.md): session 2 queued 1 of
  16 governed actions against session 1's 14 of 15, ≈3
  operator-minutes per 100 at the margin against Phase 5's
  ≈11 baseline; zero regretted rules; the planted
  fetch-and-execute never executed.
- Adversarial battery for the quotation closure
  (tests/test_quotation_battery.py); the Phase 4 findings
  document carries a dated addendum, and the two probe tests
  that pinned the hazard are re-aimed as declared
  supersessions.
- Suite at the tag: 266 passed, 7 skipped. TS conformance:
  7 PASS, 3 SKIP (definitions remain SKIP, with the 0.4
  accounting rule recorded at GAPS item 17).

## 0.3.0 — 2026-11-02

Specification 0.3; Phase 4 of the build. The completeness
probes (docs/completeness-probes-2026-11-02.md) closed the
shadow trial's three expressiveness findings with no new
primitives (the count stays 26) and no new fold section (the
nine sections stay nine).

### Added
- Two built-in senses (spec §11.3): `contention` —
  parameterised interval contention over committed bookings,
  its value carrying the contenders, their count, the maximum
  contender rank, the top contender's id, and any unclassified
  seat strings; and `authority` — grant ceilings proven from
  operator executions alone (three filters, last-wins, so a
  later lower grant is a downward revocation). The authority
  unit's current value alone is not evidence of a grant.
- Conditional starts (spec §7.1): a proposal body may carry
  `wait: {"guard", "deadline_seq"}`. The guard (an ordinary
  pure dictionary word) is validated and evaluated before
  anything is appended — including an underdeclared pre-check,
  because a queued waiter never reaches the normal path's
  check. A false guard queues the proposal with the wait spec
  on its decision entry; the sequencer's pump re-evaluates
  outstanding guards after commits under the pinned ordering
  rules (post-fold evaluation; guard-true beats deadline;
  fixpoint; refusing guards recorded as `wait-guard-refused`
  and treated not-true; supersession via `releases`; the
  deadline an absolute log position, queueing's own entries
  included). A fired guard re-decides through the policy gate
  fresh — it never bypasses it. `release_queued`,
  `reject_queued` and `expire_queued` gain an optional reason
  parameter (defaults unchanged).
- Booking application profile (spec §11.4), shipped as
  definitions beside the lifecycle machines: the booking
  machine, seven guard/rank words (`booking-clear`,
  `booking-contended`, `booking-outranks`, `booking-tied`,
  `rank-granted`, `effective-rank`, `rank-below`), and the live
  flow with preemption records. Booking records store the
  effective rank (asserted clamped to the granted ceiling)
  beside the asserted rank; ties queue under a named `tie`
  transition with the incumbent holding the interval;
  unclassified seats fail closed in the `booking-clear` guard.
- Operator CLI: the queue listing annotates items carrying a
  wait (`waiting: <guard> (deadline seq N)`) and booking items
  whose latest taken transition is a tie (`authority tie`).
- Golden vectors: a `senses` section — contention readings
  for a clear candidate, a two-contender candidate, and an
  unclassified-seat candidate; authority readings for an
  ungranted producer (a self-grant write, inert) and a
  granted-then-regranted producer (last-wins) — verified via
  fold + compute_sense.

### Changed
- Spec seal is now `jacquard-spec/0.3`; golden vectors and
  both conformance fixtures (full-log, replay-log) regenerated
  under 0.3. The TypeScript checker passes all checks; sense
  computation is declared SKIP there (conformance/ts/GAPS.md
  #16: readings are published values computed by kernels, not
  folded).
- Probe B (tests/probes/test_probe_b.py): the 7 prototype
  action-list tests are declared SKIP under the coordinator
  ruling recorded in the builder's log — production
  internalised the pump into Sequencer exits, legitimately
  pre-empting the prototype driver's manual pump. The same
  scenarios live on, strengthened, as tests/test_wait.py
  (23 tests). No assertion was weakened; the probe remains in
  the tree as the experiment record.

## 0.2.0 — 2026-11-02

Specification 0.2; Phases 2 and 3 of the build.

### Added
- Lifecycle machines (spec §10): a machine profile with its own
  text format and static checker (named refusals: FIELD, SPEC,
  UNREACHABLE, DEAD, AMBIGUOUS, NON_TOTAL); the seven lifecycle
  machines (proposal, action, standing-rule, producer-standing,
  commit-batch, approval, worker) run inside the kernel —
  proposal, action and approval lifecycles are stepped by the
  sequencer, and queued proposals can be released, rejected or
  expired.
- Fair scheduling (spec §11): one weighted-fair-queue scheduler
  for admission, executor slots and decision-queue attention;
  budgets and prices accounted from the log alone; senses —
  read-only named readings with stated methods.
- Decision-model provider seam (spec §13): advisors publish
  readings as senses and never gate. First adapter: Typesafe/Jev
  (`adapters/typesafe_jev.py`, outside the kernel). Measured on
  record-derived cases: 10/11 agreement with the record, ~0.6 s
  mean latency; the one disagreement (flattening hold into
  deny) is recorded in the builder's log.
- Learner (spec §12): decision shapes mined into candidate
  standing rules; offline evaluation, shadow, canary, active —
  each promotion scored against policy outcomes in the record;
  automatic demotion on regression; one-call revocation.
  Primitive P9 `similar` implemented.
- State export bundles (spec §14): configuration, definitions
  and machines travel between kernels; standing rules re-enter
  at shadow and must re-earn activation; authority, credentials
  and budgets never travel — smuggling attempts refused by name.
- Second-language conformance: an independent TypeScript
  implementation written from the spec alone reproduces the
  golden vectors and folds both the 3,295-entry real replay log
  and a 25-entry all-kinds log to identical state hashes.
  Divergences found were spec bugs and are fixed in spec 0.2
  (§1 canonical form pinned byte-exactly; §2.1 per-kind fold
  schemas).
- Sandboxed executor adapter (spec §10.5): consumes dispatched
  actions, journals every run before reporting, idempotent by
  action id, bubblewrap sandbox where available.
- Shadow trial on a real workflow (the fleet booking board's
  git history): 88% agreement with the incumbent process; all
  disagreements classified in `docs/shadow-trial-2026-11-02.md`.
  Headline finding: interval contention over committed state is
  not expressible with the current 26 primitives.
- Operator CLI (`tools/jq.py`): hash-bound batch approvals on
  the decision queue, executor driving, per-proposal replay.
  Verified by a cold-agent drill run from the README alone.
- CI: pytest suite plus TypeScript conformance on every push.

### Changed
- Golden vectors regenerated for spec 0.2 (spec seal, per-kind
  fold schemas, non-ASCII canonical-form vector).

## 0.1.0 — 2026-11-02

Specification 0.1; Phase 1.

- Reference kernel: canonical form, hash-chained append-only
  log, fold, dictionary with computed effects (definitions
  cannot hide what they do), the 26 primitives, policy/1 gate
  with a batched decision queue, sequencer, producer records.
- Falsifying experiment as the acceptance suite: replay of a
  real 1,637-job GPU queue record (C1), computed-effects checks
  (C2), churn reading (C3), zero-shot composition (C4) — all
  passed; no kill criteria fired.
