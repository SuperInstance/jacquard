# Phase 17 findings — in practice

Programme: Jacquard Phase 17. Charter: BUILD-BRIEF-PHASE17.md
(Casey, 2026-11-04, "experimentation and understanding through
practical knowledge"). Phases 15-16 measured governed weight
patching on batteries. Phase 17 put the grown specialists on
real fleet traffic under governance and recorded what practice
taught. Every criterion was pre-stated and hash-bound into the
governance log (experiments/wsp3/CRITERIA.md) before the test
it governs ran. Canonical log: 279 -> 356 entries.

## The headline table

| workstream | battery claim | live measurement | verdict |
|---|---|---|---|
| W1 model/code dial specialist | 84.2% held-out | 27.3% vs blind grader on real traffic (incumbent 30.3%); model class dead (0/26) | did NOT survive contact |
| W1 panic dial specialist | 50.8% held-out | 59.1% vs grader; incumbent (always calm) 63.6%; only alarmed vision in the system (7/24, 64% precision); stampede precision 0/3, zero gold | survives the letter of its bar; loses to the majority baseline |
| W1 re-coaching round 2 | predicted live 55-70% | live 34.85%; battery retention 71.67% (-12.5) | DENIED in governance |
| W2 new joint | n/a | no fleet workflow carries >=500 judgement-bearing labelled events; nearest record (bridge submissions) totals 17 | measured refusal; patcher stood down |
| W3 jev judge hygiene patch | profile: G1-upper -31.5 pts, G2-reorder -34.6 pts | sealed held-out: 84.58% operator / 78.45% correctness vs incumbent 49.79% / 42.24%; HOLD recall 0/120 -> 108/120 | shadow bar PASSED; adoption is Caseys (packet) |

## What practice taught that the bench could not

1. **The wild traffic is a different shape, not a noisier
   sample of the battery.** The dial battery was short
   messages; the fleets real agent traffic is long documents
   (156 distinct messages in the entire agent-inbox history;
   median 7,048 chars; three items near 30,000 chars). On
   long documents the incumbent dials collapse by mechanism
   (lexicon saturation -> code 153/156; a room dial adapted
   to single messages caps below its stampede band ->
   calm 156/156), and the coached specialist, fitted to the
   short shape, collapses with them (predicted code 55/66
   against a grader who found code substance in 20/66).

2. **The class boundary itself moves.** Two independent
   blind readers, labelling disjoint live sets, drew the
   code/mixed/model boundary in different places (grader:
   mixed 20/66; teacher: mixed 1/25; the cumulative
   prospector logs are model to one reader, mixed to the
   other). On batteries the labels were by construction and
   the boundary was never contested. In practice, a joint
   whose teachers disagree about its central class cannot
   be coached onto the boundary — re-coaching round 2
   repaired its diagnostic set (88.0% in-sample, model 8/9)
   and transferred almost none of it (live model 4/26,
   mixed 0/20).

3. **Incumbent reputations are sample artefacts.** The
   jev-semantic judges standing reputation (10/11 against
   ground truth, Phase 2) came from a small favourable
   sample. On the full decision record (165 items) the
   incumbent agrees with the operator 56.36% of the time,
   with correctness 42.02%, and two of its three verdict
   classes are dead (HOLD 0/38, DENY 0/8). Its input
   contract truncates the question away on 97.6% of real
   items. None of this was visible until the judge was
   profiled on its own jobs traffic.

4. **Volume is not judgement.** The fleets largest labelled
   record (gpu-queue, 1,651 jobs) is 99% one mechanical
   feeder class whose label is printed verbatim in every
   input (zero-shot student: 1.0000) with a 1,649/1
   success/failure outcome split. The judgement-bearing
   records are thin by two orders of magnitude: 17 governed
   bridge submissions, 13 governed bookings with exactly 1
   real contention event, 25 inbox tasks ever. A new joint
   needs a workflow that DECIDES often, not one that runs
   often. (W2s battery + harness stand ready; the trigger
   is the bridge record reaching ~500 submissions.)

5. **This fleet under-reports its own alarm.** The blind
   grader found 24 alarmed items and zero stampede; the
   two nearest-stampede documents were compounding
   multi-front failures logged in a routine tone. Any
   tone-reading sense will systematically under-read this
   fleets alarm state; the panic specialists wild value is
   real but bounded (it caught 7 of 24 alarms the incumbent
   could not see at all).

## Where the battery numbers survived, and where they did not

Survived: the panic dials ordering (a grown specialist sees
alarmed structure its incumbent cannot: 7/24 vs 0/24); the
W3 patch familys core claim (format/framing failures yield
to authored readout edits with retention engineered — on
sealed surfaces: +34.8 pts overall, HOLD resurrected from
0/120 to 108/120); the governance machinery itself (every
stage transition this phase — 2 deployment proposals,
1 approved, 1 denied, 6 evidence bundles — replayable from
one log).

Did not survive: the model/code specialists 84.2% (27.3%
live; the single largest bench-to-wild collapse in the
programme), its mixed class (75% battery -> 3/20 then 0/20),
the jev judges 10/11 reputation (56.4% on its full record),
and the assumption that re-coaching on wild data repairs a
drifted joint at battery prices (+7.6 live points bought at
-12.5 retention points, denied).

## The maintenance rhythm of a grown joint, in numbers

One drift cycle, fully costed by role (agent time):
detection = one shadow harness + one blind grading pass
(the grading labour — a fresh reader labelling 66 long
documents — is the expensive, non-optional part; agreement
without an independent reader is the two collapses above
nodding at each other). Trigger evaluation = free (the bar
was pre-stated). One re-coaching round = 25 fresh blind
labels + a patcher session + coordinator scoring on two
held-outs (~25 min of wall time on the Thor across three
driver iterations, because long GPU runs on the shared bench
are SIGTERM-killed and must be chunked — an environment tax
recorded in OPERATIONS.md). Governance = 2 proposals,
2 decisions, minutes of operator time. Total cycle: well
inside a day of agent time, dominated by labelling and
grading, not by patching. The rhythm is affordable; this
cycle also shows its limit — when the drift is a class
boundary dispute between the teachers, no cadence of
re-coaching fixes it. The joint must be re-chartered
(boundary adjudicated first, document-shaped battery), not
merely re-coached.

## Governance, whole phase

Canonical log 279 -> 356 entries. Criteria hash-bound
before tests (entry at 286). Evidence bundles: W1 shadow,
W1 grading, W2 inventory, W3 profile, W3 patch, W3 sealed
shadow scores, W1 round-2 scores. Deployment proposals: 2 —
W3 hygiene shadow deployment APPROVED (hash-bound), W1
re-coaching round 2 DENIED on coordinator scoring. Nothing
was promoted into a serving role; the adoption packet
(experiments/wsp3/ADOPTION-PACKET.md) is the phases closing
deliverable and the decision is Caseys.

## Limits and defects, stated

One bench (Thor), one traffic corpus (156 items — the whole
of it, but small), one blind grader per measurement (reader
dependence measured between the two readers, not eliminated).
W1s shadow window is the recorded history plus the phases
own hours; no dial consumer exists, so no specialist served
a live request. W3s fresh-input set was empty (no post-E8
decision record exists to extend the core set without
inventing context) — its shadow verdict rests on sealed
variants of seen bases plus a grouped cross-fit, both
labelled as such wherever quoted. Environment defects:
the Thor kills long GPU runs with SIGTERM (cause unknown;
chunked scoring is the standing workaround), the Oracles
root disk was 100% full throughout (lanes worked from /tmp
and bundle relays; nothing was lost), jev-rack was started
by a party outside this phase while it ran (its judge data
still hashes pristine — the incumbent was never touched),
and two workers deliveries arrived by in-report relay
because their pushes were credential-blocked (files
committed by the coordinator, byte-identical to the
workers own commits, noted at each commit).
