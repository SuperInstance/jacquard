# Phase 17 — joints in service: operations record

Kept as it accrues. Every shadowed or canaried specialist, its
live score series, drift events, re-coaching rounds and their
governance outcomes, operating costs. Charter + criteria:
BUILD-BRIEF-PHASE17.md, experiments/wsp3/CRITERIA.md
(hash-bound in the governance log before any test ran).

## 2026-11-04 — phase opened

- Thor booked (gpu bursts + box light, schedule board commit
  7504435). Canonical governance log resumes at 279 entries.
- Verified at charter: no live dial consumers in the fleet
  (W1 runs on the briefs named substitute — agent-inbox
  traffic through the same dial architecture — labelled as a
  substitution in every report); jev-rack service inactive
  (W3 runs the judge artefact standalone from a copy); Thor
  disk 28G free.
- Specialists under shadow: none yet. W1/W2/W3 building.

## 2026-11-04 — W3 profile landed (jev-semantic judge)

- Core set fixed before measurement: 165 decision items (the E8
  battery verbatim; extension to post-E8 record attempted, none
  addable without inventing context — recorded). sha256 0d51abaa.
- Baseline on the job's own score, dual: operator agreement
  56.36%, correctness 42.02%. HOLD 0/38, DENY 0/8 — both classes
  dead in the incumbent; the 64-token input window drops the
  [QUESTION] section on 97.6% of core items. Diagnostic-era
  agreement 41.96% vs held-out-era 86.79% (era mix differs).
- Profile: G1-upper −31.52 pts (retention 0.449), G2-reorder
  −34.55 (0.473), G2 all −13.64 (0.667); G1 aggregate −0.45
  (truncation is a non-problem). PATCH GATE: PASS (bar ≥5).
  Evidence entered in the governance log (293 entries).
- Hygiene patch round opened with a separate patcher role;
  surface = /head/Gemm, 771 scalars; sealed variant halves
  (480 items) held by the coordinator for post-patch scoring.
- Environment deficit recorded: Oracle root disk 100% full —
  worker clones live in /tmp/tmpfs and relay via bundles;
  nothing lost. phase17-practice push omission caught and
  fixed by the coordinator the same hour.

## 2026-11-04 — W2 closed: measured refusal (no joint qualifies)

- Pick rule applied to counted inventories. Booking-board
  contention: 13 governed units, 6 evaluations, exactly 1 real
  contention event — short of (a) by ~487. Agent-inbox routing:
  25 tasks ever, 22 claim commits — short by ~475, and no hard
  spine gates claiming. gpu-queue job-shape: 3,320 events but
  substance fails — see below. NO candidate picked; nearest
  miss named and priced, per CRITERIA.
- gpu-queue anatomy: 1,651 jobs = 1,635 feeder + 16 finite.
  The only balanced >=500 class (foundry archetypes, n=1,637)
  prints its label verbatim in every input (13 digit-normalised
  templates in the whole corpus; all 492 held-out items have
  their template in diagnostic). Outcomes: 1,649 success /
  1 failure — no failure class exists. The judgement-bearing
  record (Jacquard bridge submissions, slices 22/25) totals
  17: allow 10, deny 5, held 2.
- Battery built for the nearest miss regardless (diagnostic
  1,145 / held-out 492 sealed, sha256 2a669782): incumbent
  1.0000 on both splits, zero-shot student 1.0000 on
  diagnostic. The shadow bar is unreachable BY CONSTRUCTION —
  there is no judgement for a patch to install. Patcher stood
  down; harness stands ready for the day governed bridge
  submissions reach 500. Cost ~30 worker-min, 0 teacher calls.
- Evidence entered in the governance log (300 entries).

## 2026-11-04 — W3 hygiene patch: shadow verdict PASS

- Reachability probes (patcher, separate role): both failing
  classes head-reachable ONLY via a pooled readout (grouped-CV
  probe 94.93% vs incumbent ~23%); bias-only not reachable.
  Per-class candidates A/B each fixed their target and
  collapsed whitespace ALLOW recall to 0.0% / 3.1% — rejected
  as transfers; combined candidate C delivered (771 scalars,
  dense readout refit, L2-to-incumbent lambda=0.01).
- Rollback proven before shadow: byte-exact restore
  (.onnx 0fc8b8dc / .data 53da6a3e = pristine), 675/675
  rescored rows identical. Shadow deployment proposed and
  approved in the governance log (hash-bound, entry ~319).
- Coordinator sealed scoring (480 items, patcher never saw
  them): incumbent 49.79% operator / 42.24% correctness;
  patched 84.58% / 78.45%. Upper 26.25 -> 77.50, reorder
  21.25 -> 83.75 on unseen surfaces. HOLD recall 0/120 ->
  108/120; DENY 4/36 -> 33/36; ALLOW 235/324 -> 265/324.
  Shadow bar (CRITERIA W3): PASS, no class traded away.
- Honesty rails kept visible: core scores are in-sample
  (patcher trained on core); unseen-base estimate is the
  grouped cross-fit (core 90.91 / upper 84.71 / reorder
  84.71); sealed = unseen surfaces of seen bases. DENY
  evidence is thin (36 sealed items, 12 training rows).
- Retention accounting (core): 79/165 verdicts moved —
  70 toward gold, 8 away (named; 7 are gpu-windows ALLOW->
  DENY), 1 wrong-to-wrong.
- Environment event: jev-rack service found ACTIVE at phase
  end — started outside this phase (not by any Phase 17
  worker; verified). Its judge data still hashes pristine:
  the serving incumbent is the UNPATCHED judge. The patched
  copy exists only in ~/wsp-exp17/w3p/judge-patched/.
  Promotion = Caseys decision (adoption packet).

## 2026-11-04 — W1 shadow: battery numbers meet real traffic

- Corpus: ALL 156 distinct agent-inbox messages in the full
  git history (300 target unmet — only 156 exist; criteria
  fallback invoked, stated everywhere). 91/156 scorable per
  specialist (<=8,192-token prompt cap, never truncated);
  median item 7,048 chars — long documents, not messages.
- Live agreement specialist-vs-incumbent: mc 72.5%, panic
  78.0% (n=91). Both incumbents collapse in the wild: mc
  incumbent says code 153/156 (lexicon saturation on long
  documents); panic incumbent says calm 156/156 (max reading
  0.2354; stampede structurally impossible in the
  single-message adaptation of a room dial).
- BLIND GRADING (separate role, n=66) — mc dial: specialist
  agreement with grader 27.3% vs battery 84.2%; incumbent
  30.3%. Model class DEAD for the specialist in the wild
  (0/26 gold; predicted once in 156). Mixed recall 3/20
  (battery 75%). SURVIVES-CONTACT: FAIL. RE-COACHING
  TRIGGER: FIRED (-56.9 pts).
- Panic dial grading: specialist 59.1% vs incumbent 63.6%
  (always-calm baseline). Bar agreement half passes; the
  specialist is the only alarmed vision in the system
  (recall 7/24, precision 64%) and pays 10 calm items for
  it. Stampede: no gold in sample (recall undefined);
  specialist precision 0/3. Trigger NOT fired. Grader note
  kept: this fleets traffic logs compounding failures in a
  routine tone — tone-reading dials under-read it by design.
- Re-coaching round for the mc dial opened under governance:
  diagnostic = 25 live eligible non-sample items, being
  labelled blind by a fresh teacher role; the graded 66 stay
  sealed as round 2s held-out. Battery held-out re-scored
  after the round as the retention check.
- Environment defects logged: R4 scorer SIGTERM-killed 3x
  as a long Thor run (cause unknown; completed via 16
  micro-chunks, harness unmodified); Oracle disk full
  (worker clones in /tmp); grader push credential-blocked
  (labels delivered in-report, committed by coordinator,
  byte-identical to grader commit 6439a9e).
