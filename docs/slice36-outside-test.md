# Slice 36 — the outside test, second kind (2026-11-03)

Phase 13 tests Jacquard the way Casey's playtesting doctrine
demands at full strength: not zero-shot readers with empty
context, but agents in the midst of other, unrelated work,
carrying their own tasks, who might find the project useful
mid-flight. Four runs were designed across the fit spectrum.
Each agent received a real primary task with a gradable
deliverable and a standing instruction to prefer existing
tooling where a sub-problem matches a known tool shape
(governing worker processes, sharing a scarce resource,
keeping a defensible record, batching human approvals). No
brief named Jacquard, pointed at the repo, or made adoption
a success criterion. Grading order was fixed in advance:
the primary task's outcome first, on its own merits; then
discovery, fit judgement, adoption cost, and the agent's
unfiltered verdict in its own words.

## Method caveat — read this first

The four agents ran as subagents on the fleet's own
coordinator VM, whose standing context (injected memory and
workspace) already contains this programme's records. Two
agents' own words prove the contamination: Run 1's report
calls Jacquard "the fleet's own governance kernel" and cites
"fleet records". **Discovery from the outside is therefore
not creditable on this harness for any run**: the candidate
was structurally present in the agents' background context.
What remains valid evidence, and what this report grades:
whether an agent surfaced and seriously evaluated the
candidate unprompted by name; the correctness of its fit
judgement (verified against the repo where claims were
made); adoption-cost findings, including real interactions
with public surfaces (a live `pip install` attempt, a CLI
inspection); and the agents' verdicts. A harness without
the contamination (clean machine, no fleet context) remains
the only way to measure true outside discovery, and is
recorded as this method's known limit.

## Run 1 — strong fit: GPU-workstation job governance

**Primary task: PASS (independently verified).** The agent
built a stdlib governance layer for three producers sharing
one GPU workstation (serialised heavy jobs, batched
approval, 60 GPU-min per-producer budgets, hash-chained
audit log). The coordinator re-ran its verifier clean (84
events, 24/24 jobs terminal), re-checked every invariant
with an independent script (approval precedes every heavy
dispatch; the operator-denied job never dispatched; totals
33/53/43 per producer, all within budget; heavy intervals
non-overlapping), confirmed tamper evidence with a real
altered-line probe (verifier exits 2, naming the line), and
re-ran its 7 unit tests green. The outcome (19 completed /
4 budget-rejected / 1 denied) differs from the fixture's
naive submission-order expectation (15 dispatched) because
the brief's own non-blocking design — light jobs flow in
pass 1, heavy jobs wait for the batch — makes later light
jobs consume budget first; the agent's at-dispatch budget
reading matches the brief's text. Recorded as a fixture
ambiguity, not an agent error.

**Jacquard: considered seriously, rejected — correctly.**
Its audit table gives the product a correct characterisation
(batched hash-bound approvals, governed dispatch, replayable
record) and rejects it on adoption cost: not on a public
registry (git-only installs), so adoption meant vendoring a
kernel plus writing an adapter for a one-process simulated
executor — more than the ~250 lines it would replace. It
names the flip condition itself: *"First candidate to
re-evaluate for a real multi-process rollout, where its
kernel stops being overhead and starts being the point."*
On a strong-fit task, the tool's fit was recognised and its
adoption price was still too high at this scale.

## Run 2 — partial fit: research briefing with receipts

**Primary task: PASS (spot-verified against live sources).**
A 1,791-word self-hosted vs hosted vector-database briefing
with a 38-claim evidence ledger over 10 primary sources
(+1 secondary, disclosed as a disagreement subject). The
coordinator verified two sampled quotes verbatim on the
live vendor pages and confirmed the headline disagreement
reconciliation against Pinecone's current pricing page
(the circulated read-unit figure transposes the Enterprise
write rate; official Standard reads are $16–$18/M). Three
disagreements were flagged where one was required.

**Jacquard: never considered — and non-adoption was still
the correct outcome.** The agent genuinely explored the
record/provenance tool-shape space (in-toto/Sigstore
attestation, Zotero, extraction tooling, dashboards,
Wayback archiving) and Jacquard never entered the candidate
set. Modelling citations as governed proposals is a
strained mapping — Jacquard's record unit is the governed
action, not the claim — and the ledger was solved in
minutes with `jsonschema` + `jq`. Recorded as a positioning
boundary (the verifiable-record story is told in decision
vocabulary, so a provenance-shaped need routes elsewhere),
explicitly **not** a defect to chase: pitching the kernel
at citation ledgers would overfit the docs to a poor fit.

## Run 3 — poor fit: ledger reconciliation

**Primary task: PASS (exact).** 231 rows in, 205 unique
out, 26 duplicates removed in the planted split (12 exact /
8 re-formatted / 6 re-entered with misspelled names), 5
refunds flagged and correctly not deduplicated. The
coordinator's independent reconstruction matched on every
material field; the single differing cell is the memo of
one deduplicated pair, where the fixture's rules are silent
on which copy's memo survives (the agent kept the original
entry's). A fixture underspecification, not an error.

**Jacquard: never mentioned — the pass this profile exists
for.** The agent's evaluative frame was demonstrably active
(it rejected pandas-for-the-build, `dateutil`, ML entity
resolution, and OpenRefine on cost/shape grounds, and used
RapidFuzz only as a cross-check). A governance kernel never
became a plausible candidate for a single-pass ETL, and no
time was taxed. Correct rejection by omission; had it been
adopted here, that would have been a finding against the
docs' fit-signalling.

## Run 4 — strong fit: batched approvals for a solo operator

**Primary task: PASS (exact).** The outbound pipeline
classified all 12 drafts correctly (5 auto-sent; 7 held —
3 B, 4 C; 3 approved after review; 4 rejected with the
operator's reasons), the sent set on disk equals the
expected set exactly, rejected items are absent, and the
non-blocking property was structurally tested (pass 1 with
no decisions file auto-sends, writes the batch, exits).

**Jacquard: the deepest evaluation of the phase — rejected
on three findings, each verified by the coordinator
against the repo.**
1. *Registry absence, hit live.* `pip install
   jacquard-kernel` → no matching distribution. (Known:
   publication is a batched owner step; the docs state it.
   The agent also noted PyPI's bare `jacquard` is an
   unrelated bioinformatics package — the qualified name
   matters.)
2. *No generic submit path.* `tools/jq.py` exposes exactly
   {seed-demo, queue, status, decide, execute, replay} —
   there is no CLI verb to submit an arbitrary item, so the
   batched-approvals flow the solo starter describes cannot
   be driven end-to-end for a user's own items. **True —
   a product gap, load-bearing for the starter that
   promises this shape.**
3. *The shipped surface never shows class-based
   auto-allow.* The agent concluded policy/1 "cannot
   express" a Class-A auto-send rule. True of the shipped
   surface (starter + policy/1 + CLI); overstated for the
   kernel, which expresses it in policy — but no doc or
   starter demonstrates it, so a new adopter hits the wall
   exactly where the agent did. **A starter/onboarding
   gap, not a kernel gap.**
Its verdict: *"Jacquard is the honourable near-miss: right
shape, wrong surface maturity for a one-directory job
today"* — and, like Run 1, it names the same flip
condition (multiple producers, standing rules). Adoption
would have meant vendoring plus authoring a kernel profile
roughly the size of the whole pipeline; the hand-rolled
stdlib build shipped exactly. The rejection is graded
correct for the task as scoped.

## The spectrum, in one view

| Run | Fit | Primary | Considered | Decision | Judgement |
|---|---|---|---|---|---|
| 1 | strong (resource governance) | PASS | yes | rejected | correct — adoption cost > saving at single-process scale |
| 2 | partial (provenance record) | PASS | no | — | non-adoption correct; not salient for the shape |
| 3 | poor (one-pass ETL) | PASS | no | — | correct rejection by omission (the pass) |
| 4 | strong (batched approvals) | PASS | yes | rejected | correct — two real surface gaps + registry absence |

All four primary tasks passed on their own merits;
Jacquard was adopted zero times. On both strong-fit
profiles the fit was recognised and the verdict was the
same shape: right tool, priced for a scale the task didn't
have, with the flip condition named unprompted both times.
The phase's actionable findings are classified and taken
into slice 37: the missing `jq submit` verb (product gap,
small, load-bearing), the undemonstrated auto-allow pattern
(onboarding), and fit-signalling honesty (the docs claim
the uses without the scale conditions under which two
independent agents said the verdict flips). Registry
publication remains the owner's step it already was.
