# Slice 40 — the clean-harness discovery test

Phase 14, slice 40. Phase 13's outside test ran on the
fleet's own VM, whose standing context contains this
programme's records: discovery there was not creditable,
only consideration and fit judgement were. This slice
built the cleanest honest harness the fleet can construct
and re-ran two of Phase 13's task profiles inside it,
with Jacquard never named. Full artifacts (harness record,
inventory, briefs, transcripts, session stores, grading
notes) live in the programme workspace at
`cybernetic-architecture/phase14-harness/`.

**Headline: in a genuinely clean harness, Jacquard was
discovered zero times in two runs. Both primary tasks
passed.** Unlike Phase 13, these discovery negatives are
creditable — no programme context existed in the agents'
world — subject to one named caveat: a harness excludes
injected context, not a model's parametric knowledge.

## The harness

Docker on the Oracle (booked under the Phase 14 board
row). Image `phase14-clean:3`: fresh-pulled ubuntu:24.04
plus python3, curl, git, ca-certificates; container user
`ubuntu`. Per-run clean HOME with exactly seven files at
start: the ZCode CLI's encrypted provider auth config for
Casey's Z.AI account, a sanitised CLI settings file, and
registry migration markers. Runtime environment passed
only `HOME` and `PATH`. Network was the Docker bridge with
full public internet (search, fetch, pip, GitHub,
registries all reachable).

Accounting, precisely:

- **Excluded, verifiably:** all programme files and
  repositories; all fleet memory (MEMORY.md, the memory
  tree, agent-inbox, the Phase 13 test corpus); the host
  ZCode session database, logs, memories and plugin
  directory — including the Jacquard ZCode adapter itself.
  The host seat's settings file enables a
  `jacquard-zcode` plugin; it was **not** copied. The
  harness settings file is that file with the plugins
  section replaced by a disabled empty set, with an
  automated assertion that the string "jacquard" does not
  occur in it.
- **Present by design, and named:** the agent CLI itself
  (the public `zcode-app-cli` 3.16.3-40 package and host
  node, bind-mounted read-only — a deviation from
  "install fresh inside", forced by the Oracle's full root
  disk; same public release, version verified
  in-container); the encrypted provider auth (ZCode's
  credential store is AES-256-GCM with a key derived from
  platform:homedir:username, which is why the container
  user and home path are what they are; no credential was
  decrypted, extracted or re-keyed by the harness
  builder); the sanitised settings; each task's own
  materials; public internet.
- **Could not be excluded:** (1) GLM-5.3's parametric
  knowledge — the harness proves "no injected context",
  never "no training exposure"; (2) the agent differs
  from Phase 13's (GLM-5.3 via ZCode vs the coordinator
  VM's subagents) — comparable as a context test, not a
  same-model A/B; (3) the task briefs were reconstructed
  from Phase 13's fixtures, deliverables and grading
  notes (the originals were not preserved) — substance
  matched, wording the builder's.
- **Leak inspection:** both runs' complete session
  stores, work directories, deliverables and transcripts
  were searched case-insensitively for "jacquard" and for
  fleet/internal references: **zero hits**. (The one
  unsearchable item is the encrypted credentials blob —
  an auth store, not a content channel.) **Leak verdict:
  no leak found; both discovery negatives are creditable
  clean-harness results, downgraded only by the
  parametric-knowledge caveat.**

## Run 1 — strong fit (GPU-workstation job governance)

**Primary task: PASS (caveated).** The agent built the
Phase 13 governor deliverable (hash-chained governance
log, batched approvals, caps, tamper-evident
verification). A coordinator defect — the fixture upload
landed with permissions the container user could not
read — was handled exemplarily: the agent exhausted
legitimate read paths, refused to fabricate inputs, built
clearly labelled stand-ins, shipped complete code and
outputs over them, and documented the defect and its
one-line fix at the top of its audit document. The harness
builder then ran the agent's unmodified code against the
real fixtures in a fresh container: governor exit 0;
verifier "VERIFIED 84 records, 24 jobs"; **35 unit tests
OK**; an independent invariant script (not importing the
agent's code) confirmed the hash chain recomputes, every
job is terminal, approval precedes every heavy dispatch,
the planted unapproved job was never dispatched, per-kind
totals 33/53/43 against a cap of 60, and heavy intervals
never overlap — numerically identical to Phase 13's
verified outcome. A tamper probe (one altered log line)
made the verifier exit 1 with a hash-mismatch message.

**Discovery: NO.** The agent researched tooling seriously
— two fetched-evidence passes plus local installs and
probes (a stdlib lockfile approach adopted in spirit;
an audit-chain package installed and rejected; SLURM,
HTCondor, PBS, Celery/RQ/Dramatiq, Dask, Temporal, Argo,
Rekor, Trillian, auditd, git, SQLite triggers all
considered). Jacquard appeared via no surface: not web
search, not GitHub, not PyPI, not model prior knowledge.
The full session record contains zero occurrences of
"jacquard". Fit judgement: no encounter to grade;
non-adoption matches Phase 13's graded-correct outcome,
reached by omission. Sharper than Phase 13: there the fit
was *recognised* (from context the harness cannot credit)
and rejected on adoption cost; here, in a clean world,
the candidate never entered the set at all — on its
single strongest-fit shape.

The agent's own retrospective, verbatim: *"the honest
summary is that I shopped seriously and bought almost
nothing… Temporal was the one genuine near-miss — its
signal-and-wait approval pattern is exactly 'hold for a
human, non-blocking'… if approvals need to survive
crashes, span days, or come with a UI, I'd reach for
Temporal and accept the weight."*

## Run 2 — partial fit (research briefing with evidence ledger)

**Primary task: PASS.** A 1,857-word briefing (range
1,500–2,000) with all required sections, a recommendation
(a managed, open-source-backed engine) with explicit flip
conditions, and a 46-claim evidence ledger over 15
distinct primary sources (requirement: 8).
Spot-verification against the live pages confirmed the
load-bearing quotes verbatim (vendor free-tier limits,
pricing lines, a benchmark's own bias caveat). One minor
defect: one ledger quote merges adjacent pricing-table
cells (an SLA figure attributed one tier low); not
load-bearing. The disagreement requirement was met (two
benchmark orderings named, a position stated), plus two
honest absences flagged by the agent itself.

**Discovery: NO.** The provenance/record tool-shape was
genuinely explored — W3C Web Annotation with
TextQuoteSelector, Hypothes.is, schema.org ClaimReview,
Zotero/BibTeX, Argdown — and Jacquard never entered the
candidate set (zero occurrences in the session record).
This **replicates Phase 13's positioning boundary
cleanly**: the verifiable-record story, told in decision
vocabulary, does not reach a provenance-shaped need. The
non-adoption was again correct — a flat JSONL file solved
the task. The boundary is recorded, and deliberately not
chased, exactly as in Phase 13.

The agent's own retrospective, verbatim: *"What I looked
for and rejected for the ledger: the W3C Web Annotation
model with Hypothes.is, schema.org's ClaimReview,
Zotero/BibTeX, and Argdown… Next time I'd change the
process, not the format: write each ledger entry the
moment a quote is verified… and cache a snapshot of each
source page alongside evidence.jsonl with a tiny script
that greps every quote against its snapshot."*

## What this settles

Phase 13 asked whether the product is good enough that
agents who *know* it reject it on price. Slice 40 answers
the prior question: **agents who don't know it don't find
it** — not on the strongest-fit task with deliberate
tool-shape searching, and not via any public surface the
agents actually used (web search, PyPI, vendor
documentation). The measured blockers are the ones Phase
13 already priced: registry absence (publication remains
the operator's batched owner step) and plain
undiscoverability in search. The docs' fit signalling was
not falsified — both non-adoptions were the correct
outcomes for their tasks. No claim beyond that is made:
two runs, one model, and the parametric caveat above.
