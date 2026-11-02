# PROGRAMME RECORD — Jacquard

*The master record of the whole effort: what it is, how it got
here, what is decided, what is built and verified, what the
market evidence says, and what happens next. Written 2026-11-02
at Casey's direction ("make good documentation — we don't want
to forget all this somewhere in an old context"). This document
is the narrative spine; the loadable technical distillation is
CONTEXT-PACK.md, the market evidence is USE-CASE-VOID-SCAN.md,
and the build's own process record is docs/BUILDERS-LOG.md in
the repo. If this file and the pack ever disagree, the pack's
verified facts win and this file gets corrected.*

## What Jacquard is

A decision kernel for untrusted producers — software agents,
models, automations, people — that emit proposals differing in
cost, latency, reliability and authority. Proposals are gated by
versioned policy; a proposal's effects are COMPUTED from its
definition tree, not taken from its own declaration; every
decision lands in an append-only hash-chained log, and committed
state is a fold of that log, so any decision can be replayed and
re-derived by an independent implementation. Human approvals
batch into a decision queue — the boss decides in one pass and
no lane ever stalls waiting. Recurring decisions can become
standing rules, but only through deployment discipline: offline
evaluation, shadow running scored against real outcomes, staged
activation, automatic demotion on regression, one-command
revocation. Budgets and prices live in one accounting unit;
contended resources are scheduled by weighted fair queueing.
Definitions and rules can travel between kernels in a state
export bundle — and arrive UNPROVEN, re-entering at shadow,
because trust is local to the record that earned it. Decision
models (Jev/Typesafe and successors) are advisors behind a
provider interface: their readings are senses, never the gate.

One sentence for the door: **Jacquard decides what agents may
do, keeps the receipts to prove why, and learns from its own
rulings without ever letting the student grade itself.**

## How it got here (2026-11-01 → 11-02)

1. Casey pushed a long consumer-AI architecture conversation
   ("SUPERINSTANCE CYBERNETIC ARCHITECTURE DIAGRAM", plus a
   second "gpu-os" thread) to Muse by email and directed a
   piece-by-piece digestion. Muse grounded every claim against
   the real repos (signal-chain, pincher, exoj, cocapn/sxc1) and
   kept a credibility ledger: several cited projects were real,
   one was real-but-misdescribed (TensorDex), several had no
   trace at all. Standing lesson, in Casey's words as explained
   back to him: credibility decays with distance from his
   pushes — and resets when he re-grounds.
2. Casey directed: work all twelve open questions, find the
   flaws, keep good documents (docs 01–06); then design the next
   repo without being bound to the old ones (doc 07,
   "switchboard"); then redo it from first principles with all
   metaphors stripped (doc 08) — the design that survived;
   then fold in StateSmith-with-an-agent-as-author and the
   Forth dictionary paradigm (doc 09), which unified into one
   mechanism: extension by definition only, with computed
   effects; then the 26 primitives, two worked examples from
   real fleet history, and a falsifying experiment with explicit
   kill criteria (doc 10).
3. Casey adopted the anchored-iteration protocol for future
   chatbot work (doc 12 + ANCHOR-CARD.md): short fresh rounds
   from a verified one-page card; the transcript is compost,
   the card is the crop.
4. Casey directed the extraction of the whole record into
   CONTEXT-PACK.md + context-pack.json (facts / rulings /
   design / open / gaps / debunked, kept separate) — the entry
   point for any agent picking this up cold.
5. Casey ruled on all six open choices (2026-11-02 09:31,
   §Rulings below), directed the Foundry feeder stopped and the
   process (not the assets) judged, and at 10:20 said "get it
   built." The rest of the day: Phases 1–3 built and verified,
   a market void scan run under his usefulness direction, and
   Phases 4–5 chartered.

## Rulings (Casey's — the constitution of this programme)

1. **Build base = the clean-sheet derivation** (doc 08), for
   maximum quality in this specific application; the
   conservative distil (doc 07) is the fallback.
2. **The approval dichotomy is false.** Work never stalls for
   the boss and never silently becomes the boss: items needing
   him batch into a decision queue while everything else
   continues. (R5 amendment; also how Muse runs this lane.)
3. **Name: Jacquard.** (His proposal; a loom whose behaviour
   lives in swappable pattern cards = definitions. "Jeckard"
   in one message was voice dictation, confirmed by him.)
4. **No-downside fixes are automatic**, not decisions — he was
   surprised the pincher doc fix was even a question.
5. **No jargon lock-in.** The hermit-crab/.nail concepts were
   scaffolding for building, not the production surface;
   production naming is plain ("state export bundle"); no
   pre-trusted shell pairs in v1 (.nail keeps its name only
   inside pincher's own repo).
6. **Feeder off; judge processes, not unsupervised output.**
   Unsupervised generation degrades without environmental
   nudging; automated Foundry generation stays off until the
   process is judged (verified off; 16,667 registry rows, 39
   ever used — the churn is also Jacquard's worked example C3).
7. **Resources are already-paid capacity, use them**: fleet
   seats (MiniMax/ZCode/MCode/Claude Code), DeepInfra (cached
   iterative loops), Typesafe/Jev (advisor experiments),
   Cloudflare Workers AI (build help, play-testing). Spend
   prepaid before new money.
8. **Decision models sit behind a provider interface** —
   production users may use Typesafe or others; Typesafe is
   the first plugged-in provider, never a kernel dependency,
   and never the gate.
9. **The F1/F2 items are first-class concepts** — but add no
   more to the primitives than needed; decide by simulation
   and tests, on the escalation ladder (policy → data →
   machine → sense → one general form, proven necessary).
10. **Direction is set by use cases and voids**: uniqueness
    first, usefulness second (his extraction rules, applied to
    this roadmap). A tool people work through, not a parlor
    trick — however good its tests.

Standing process rules for the build (all Casey's, all in the
briefs): document as you go — the process record is part of the
deliverable; docs ship WITH each slice (README staleness is a
defect on par with a failing test); public by default, secrets
excepted; Muse manages and verifies, fleet agents execute;
verification means cold clones and re-run suites, and "tested"
names the artifact tested (the tag, not the working tree).

## Build state (verified by Muse, not by builder testimony)

Repo: **github.com/SuperInstance/jacquard** (public).

- **Phase 1 — COMPLETE** (main@665a57e): spec 0.1 + golden
  vectors; Python kernel (canonical form, hash-chained log,
  fold, 26 primitives, dictionary with computed effects,
  policy/1, batched decision queue, sequencer, producer
  records). The doc-10 falsifying experiment ran as the
  acceptance suite: C1 replay PASS on real gpu-queue data,
  C2 computed effects PASS, C3 churn reading PASS (output-use
  0.0 over 13,080 outputs), C4 zero-shot composition PASS.
  46 tests; no kill criteria fired.
- **Phases 2+3 — COMPLETE** (main@3ce55ff, **tag v0.2.0**,
  spec 0.2): lifecycle machines with own profile checker
  (StateSmith CLI deliberately not integrated — reason in the
  log); WFQ + budgets/prices + senses; the learner (rules
  scored against policy/1's recorded outcomes, never against
  themselves; planted regression auto-demoted); state export
  bundle (rules re-enter at shadow; smuggling refused by
  name); TypeScript conformance written from the spec only
  (7 PASS, 2 declared SKIPs); sandboxed executor (bubblewrap,
  idempotency by action id); **live shadow trial on the real
  booking-board history — 46/52 agreement (88%), disagreements
  classified 3 policy-gap / 3 incumbent-wrong (real double-
  bookings)**; operator CLI with hash-bound approvals;
  cold-agent drill passed after 6 defects fixed; CI green;
  release verified from the tag artifact (Muse's own cold
  clone: 128 passed). **Jev experiment: 10/11 agreement with
  record ground truth at 0.6 s mean — the one miss flattened a
  HOLD into a DENY, the exact distinction the design treats as
  load-bearing; advisors-as-senses confirmed empirically.**
- **Phase 4 — RUNNING**: completeness probes for the two
  findings the shadow trial produced — F1 interval contention,
  F2 conditional starts + authority priority — simulations and
  adversarial tests first, findings doc before any spec
  change, only the winning minimal set implemented.
- **Phase 5 — CHARTERED, starts when Phase 4 lands**:
  beachhead-1 build-out (live coding-agent adapter, network
  service, batched queue notifications, measured proof run).
- Known deficits (the honest list): 2 conformance SKIPs (a
  full TS port closes them); learner quarantine has no driver
  yet; V1 coverage partial for raw proposals (GAP-3); F1/F2
  open until Phase 4 reports; no network service or live
  adapter yet (Phase 5); the /tmp incident in Phase 3 (an
  unpushed commit lost to a VM reset; fixture regenerated
  bit-identically; push-per-slice is now absolute).

Four additive doc fixes to the older repos were also landed
under ruling 4 (pincher 79bc5b3, signal-chain f113fbf, exoj
e596ac3, cocapn a399d6b) — the design record's fix list is
closed.

## Market evidence (summary — full record: USE-CASE-VOID-SCAN.md)

25 products surveyed from primary documentation across agent
frameworks, durable execution, policy/guardrail layers,
observability/governance, standalone authorisation services
and agent-security products. Six voids (V1–V6, detailed in
CONTEXT-PACK §11 and the scan). Headlines: every surveyed gate
evaluates declarations rather than computed effects; every
shipped approval mechanism blocks its producer (Permit.io's
batch review queue is the nearest miss — the reviewer is
unblocked, the producer still waits, timeout = reject, and
hash-bound approval exists nowhere); "immutable" audit records
are claimed by several vendors and mechanised by none;
approval history compiling into governed standing rules was
found nowhere; earned standing has no exportable artefact in
any product. No surveyed product holds more than two of the
six properties; Jacquard's claim is the composition on one
log — simultaneously the audit record, the scoring substrate,
the bundle source and the spend ledger. Beachheads, ranked:
(1) supervision layer for coding-agent fleets run by small
teams/solo operators — the adapter slot is occupied (Cerbos
Synapse, Permit), so the wedge is the composition and
time-to-integrate; (2) "why was this allowed" evidence for
small regulated operators — proof is an independent
re-derivation audit drill; chain-head anchoring is the top
missing product piece; (3) shared expensive-resource
governance — most proven fit, smallest market, the
demonstration garden for (1) and (2).

## Open decisions and next steps

- **F1/F2 ruling** returns to Casey WITH Phase 4's probe
  evidence (which rung won per gap, measured) — batched, one
  ruling, nothing else blocked on it.
- **After Phase 5's proof run**: beachhead 2's product pieces
  (chain-head anchoring, key management, PII/redaction,
  compliance mapping) and beachhead 3 live onboarding are
  separate authorisations, decided on slice-15 numbers.
- **Standing options list** (none started): full TypeScript
  port; Rust kernel against the proven vectors; gpu-queue as
  a second workload, live not shadow; si-ready shelf
  packaging (after F1/F2, since a primitive change moves the
  spec to 0.3).
- **The .nail shell-pair exception** (doc 02/Q6 lineage) is
  formally still Casey's call in the old design record;
  ruling 5 settled the v1 answer (none) — noted here so no
  future agent resurrects it as open build work.

## Where everything lives

- This folder (`~/workspace/cybernetic-architecture/`):
  PROGRAMME.md (this record) · CONTEXT-PACK.md + .json (the
  loadable distillation) · ANCHOR-CARD.md (one-page verified
  facts for fresh rounds) · USE-CASE-VOID-SCAN.md (market
  evidence, incl. §7 hardening addendum) · docs 01–12 (the
  design passes) · IDEATION-NOTES.md (first digestion +
  credibility ledger) · BUILD-BRIEF*.md (Phases 1–5 charters)
  · email-originals/ (source emails as received).
- The build: github.com/SuperInstance/jacquard — spec/SPEC.md,
  docs/BUILDERS-LOG.md (the process record), docs/shadow-
  trial-2026-11-02.md, tests/ (incl. the real datasets with
  provenance).
- Feeder review: ~/workspace/feeder-review/ (the asset/process
  judgement page built for Casey's ruling 6).
- Memory: the durable facts live in Muse's long-term memory
  (MEMORY.md, Jacquard entry) — pointers and verdicts, with
  this folder as the evidence behind them.
