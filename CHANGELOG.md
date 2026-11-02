# Changelog

Derived from `docs/BUILDERS-LOG.md`, which remains the full
record (decisions, reasons, dead ends).

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
