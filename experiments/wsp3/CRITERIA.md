# Phase 17 — pre-stated criteria (hash-bound before any test runs)

Charter: BUILD-BRIEF-PHASE17.md (Casey, 2026-11-04). This file
was written and its sha256 entered into the canonical governance
log (experiments/wsp/governance/kernel.jsonl, producer
wsp17-harness, stage p17-criteria) BEFORE any Phase 17 test,
shadow run, or patch round. Amendments, if reality forces them,
are appended below the original text, dated, and hash-bound the
same way before the test they govern — never edited in place.

## Standing facts the criteria rest on (verified at charter)

- No live consumer of elephant/signal-chain dials exists in the
  fleet (code search across the Oracle home + GitHub, 2026-11-04:
  DialBank appears only in research notes). W1 therefore runs on
  the briefs named substitute, labelled as a substitution
  wherever reported: the fleets own agent-message flow
  (agent-inbox git history) classified through the same dial
  architecture. Battery traffic is never reported as live traffic.
- Thor residents jev-rack / comfyui / foundry-portal are
  INACTIVE services at charter; the :8001 coder is not
  listening. W3 works on a COPY of the judge artefact run
  standalone; the resident service is never started or mutated.
- Thor disk: 28G free at charter. Artefacts stay small; model
  copies already on the bench are reused, not re-downloaded.

## W1 — shadow of the two grown dial specialists

Corpus: real agent-inbox messages from the repos git history
(inbox/claimed/done/verdicts across all commits, deduplicated,
provenance = commit + path). Target >= 300 messages; if fewer
exist, all of them, and the count is stated.

Measures (shadow is measurement; these are interpretation bars,
pre-stated so the findings cannot move them):
- live agreement: specialist vs incumbent dial, overall and
  per class, on the full corpus.
- teacher spot-check: a grader who did not build the harness
  labels a stratified sample of >= 60 corpus items BLIND (no
  incumbent or specialist output shown). Report specialist and
  incumbent agreement with the grader, per class.
- SURVIVES CONTACT (per dial): grader-agreement on the live
  sample within 10 points of the battery held-out number
  (dial 84.2, panic 50.8) AND no class at recall 0 that was
  alive on the battery. Anything else is reported as drift,
  with the class mix of live traffic stated beside it (the
  live mix is not the batterys 40/40/40).
- stampede watch: panic specialists stampede recall on the
  live sample is reported by name, whatever it is.

Re-coaching trigger (all workstreams): if a shadowed
specialists live grader-agreement falls >= 15 points below its
battery held-out on the accumulated sample, or a battery-alive
class shows recall 0 in the wild, ONE re-coaching round may be
proposed through governance; its outcome (approve or deny) is
recorded either way. No silent re-coaching.

## W2 — one new joint in a running fleet workflow

Pick rule (decided before inventory results are seen): the
joint must have (a) >= 500 historical real events with labels
derivable from recorded outcomes — no new human labelling of
the training split; (b) an incumbent behaviour recorded in the
same record, to shadow against; (c) a hard spine the joint
sits inside. The worker inventories booking-board contention,
gpu-queue job-shape, and agent-inbox routing against (a)-(c)
and picks the one that satisfies all three; if none does, the
nearest miss is named and the gap stated, not papered over.

Protocol: temporal split of the historical record (earliest
70% diagnostic, latest 30% held-out — held-out never seen by
the patcher). Family-1 readout patch per Phases 15/16.
- SHADOW BAR (earns canary): held-out >= incumbent + 10 AND
  no class dead that the incumbent keeps alive (the R4 bar).
- CANARY (if the bar is met and governance approves): the
  specialists class is recorded as a sense reading alongside
  real submissions for the rest of the window; it never gates,
  never routes, never blocks. Rollback = stop recording;
  proof = the recording mechanism diff plus a replay showing
  submissions unaffected.
- Cost counted live (worker minutes, teacher calls, scoring
  runs, governance proposals/decisions) and compared against
  Phase 16s ~1 hour N+1 figure.

## W3 — profile-guided hygiene on the jev-semantic judge

Artefact: intuition_student.onnx (~/jev-rack/judge/ on the
Thor), run standalone from a COPY. The resident service stays
down and untouched.

Job score: agreement with recorded outcomes on a fixed core
set built from the Jacquard decision record (the judges real
input class: decision proposals with recorded outcomes),
dual-scored as E8 was — (a) agreement-with-operator,
(b) agreement-with-correctness where the record itself shows
the outcome. The core set is fixed before any patching.

Profile: the Phase 16 instruments discipline adapted to a
classifier judge — graded failure classes: G1-class malformed
/ format inputs (truncations, casing, wrapper junk), G2-class
framing (paraphrase / reordering sensitivity: same decision,
different surface), retention = core-set verdict stability.
All classes measured on the incumbent copy first.

- PATCH GATE: a hygiene patch is authored only if some
  G1/G2-class score sits >= 5 points below the judges core-set
  score. Patch = readout/head-level edits only, enumerated,
  reversible; retention engineered by construction (core-set
  verdicts are the retention curve; a patch that moves any
  core verdict it was not aimed at is a transfer, reported
  as such, per Phase 16s load-bearing clause).
- SHADOW BAR: patched copy >= incumbent on the jobs own score
  over the shadow input set (core set + post-Phase-15 record
  decisions as fresh inputs), no core class traded away.

## W4 — close

Operations record kept as it accrues (experiments/wsp3/
OPERATIONS.md). Findings document answers the briefs four
questions with each claim tied to a live measurement. The
adoption packet is a separate deliverable: per candidate —
live evidence, drift record, rollback proof, the exact
serving change adoption would make. Promotion into a serving
role is Caseys decision; this phase promotes nothing.
