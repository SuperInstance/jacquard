# Phase 17 — batched adoption packet (Caseys decision)

Prepared by the Phase 17 coordinator, 2026-11-04. Nothing in
this packet has been promoted. Each candidate carries: live
evidence, drift record, rollback proof, and the exact serving
change adoption would make. The governing record is the
canonical log (experiments/wsp/governance/kernel.jsonl,
356 entries); the full measurements are in
experiments/wsp3/FINDINGS.md and the workstream records.

---

## Candidate 1 — jev-semantic judge, hygiene patch (W3)

RECOMMENDATION: adopt (the phases one ripe candidate).

Live evidence. On the judges own job (the fleets decision
record, 165 items, fixed before measurement): the incumbent
agrees with the operator 56.36% and with correctness 42.02%;
HOLD and DENY are dead classes (0/38, 0/8). The patched
copy, scored by the coordinator on 480 sealed variant items
the patcher never saw: 84.58% operator agreement / 78.45%
correctness against the incumbents 49.79% / 42.24% on the
same items; HOLD recall 0/120 -> 108/120; DENY 4/36 ->
33/36; ALLOW 235/324 -> 265/324. The unseen-BASE estimate
(grouped cross-fit of the patch procedure): core 90.91%,
upper 84.71%, reorder 84.71% — quoted beside, never instead
of, the sealed numbers. In-sample core score (93.94%) is
not evidence and is not used here.

Drift record. The incumbent was not drifted so much as
never measured: its failures are standing properties —
casing sensitivity (-31.5 pts), field-reorder sensitivity
(-34.6 pts), dead HOLD/DENY — plus a contract fact the
patch does not fix: the 64-token input window drops the
[QUESTION] section on 97.6% of real items. Adoption makes
the judge robust to surface variation; it does not repair
the contract. If the contract is ever revised (longer
window), the patch must be re-earned, not carried.

Retention accounting. 79 of 165 core verdicts moved: 70
toward gold, 8 away (named in W3-PATCH.md — seven are
gpu-windows items the patch now denies that the operator
allowed), 1 wrong-to-wrong. Per-class patch candidates were
rejected during construction for collapsing an untargeted
class; the shipped candidate is the combined one.

Rollback proof. Demonstrated before shadow: restoring the
771 head scalars returns byte-identical files (.onnx
sha256 0fc8b8dc..., .data 53da6a3e... = the pristine
resident hashes), with 675/675 rescored rows identical to
the incumbent run. Rollback after adoption = the same
restore from the preserved pristine copy.

Exact serving change. (1) Back up ~/jev-rack/judge/
intuition_student.onnx and intuition_student.onnx.data
(pristine hashes above). (2) Copy the patched pair from
~/wsp-exp17/w3p/judge-patched/ into ~/jev-rack/judge/
(patched .data sha256 af8a2245..., .onnx 1bb15c5b...).
(3) Restart the jev-rack service (it is currently running,
started outside this phase, serving the pristine judge).
(4) Smoke: POST /judge on the three recorded examples in
TOOLS.md and confirm the verdict labels move from
lean/lean/settled+ pattern to the patched readings in
experiments/wsp3/w3p/results-patched.json. Constitutional
note: jev remains an advisor behind the provider seam —
this changes an advisors weights, never a gate.

DECISION: [ ] adopt  [ ] decline  [ ] adopt with conditions

---

## Candidate 2 — panic dial specialist (Phase 16 round 1)

RECOMMENDATION: do not adopt as a replacement; hold as an
evidence-ready additional sense for the day a consumer
exists.

Live evidence (blind-graded, n=66): agreement 59.1% vs the
incumbent dials 63.6% — but the incumbent is an always-calm
machine (alarmed recall 0/24) and the specialist is the
only alarmed vision measured (recall 7/24 at 64%
precision). Stampede: no gold items in the sample; the
specialists 3 stampede calls were all wrong.

Drift record. Battery 50.8% (balanced classes) vs live
59.1% (calm-heavy mix) — the number rose while the
usefulness question sharpened: adoption is a trade, 7 of
24 real alarms seen, paid for with 10 of 42 calm items
misread, per 66.

Rollback proof. The specialist is a model copy
(~/wsp-exp16/r4/round1/patched); it serves nowhere today.
Adoption would be a new integration, not a swap; rollback
= remove the integration.

Exact serving change. None available to name: no fleet
workflow consumes a panic reading today (verified by code
search at charter). Naming a serving change requires a
consumer to exist first. Recorded so the evidence is
ready when one does.

DECISION: [ ] revisit when a consumer exists  [ ] decline

---

## Candidate 3 — model/code dial specialist (Phase 15 round 1)

RECOMMENDATION: do not adopt.

Live evidence. Battery 84.2% collapsed to 27.3% against a
blind grader on the fleets real traffic — below the
incumbent dial it was grown to replace (30.3%) and below
the point where the number means anything. Re-coaching
round 2 (governed, trigger-fired) reached 34.85% live at a
-12.5 pt battery retention cost and was DENIED in the log.
The joint, as chartered on short messages, does not exist
in document-shaped traffic, and its central class boundary
is drawn differently by independent readers. Any future
adoption requires re-chartering first: an adjudicated
class boundary and a document-shaped battery.

Serving change / rollback: none — the specialist serves
nowhere; both rounds stand as artefacts in the record
(~/wsp-exp/e7/round1/patched-r1, ~/wsp-exp17/w1-r2/
patched-r2) with rollback = discard, never needed.

DECISION: [ ] decline  [ ] re-charter the joint

---

## Non-candidates, for completeness

- W2 produced no candidate: no fleet workflow currently
  carries the judgement volume a new joint needs
  (experiments/wsp3/W2-INVENTORY.md). The battery and
  harness stand ready; the named trigger is the governed
  bridge submission record reaching ~500.
- The W3 patch does not fix, and adoption should not be
  read as endorsing, the jev input contract (64-token
  window). That is a separate, larger change to a serving
  contract, outside this phases governance.
