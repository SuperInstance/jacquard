# Changelog

Derived from `docs/BUILDERS-LOG.md`, which remains the full
record (decisions, reasons, dead ends).

## 0.5.0 — 2026-11-02

Specification 0.5; Phase 7, slice 18 (chain-head anchoring).
Slice 19 (the full TypeScript port) completes the phase and is
not in this entry.

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
