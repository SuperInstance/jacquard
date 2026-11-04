# Phase 15 — Weight-Space Programming, Governed: Experiment Plan

Charter: BUILD-BRIEF-PHASE15.md (Casey, 2026-11-03) + steering
17:39 (E6 loop; E7/E8 application targets) + steering 17:41
(seat-based labour pool). Coordinator clone: ~/jacquard-p15 on
the Oracle, branch phase15-wsp, base v1.2.2 @ccaf95f. Phase 14
runs in parallel in ~/jacquard-p14; this phase rebases over its
tag at slice 43.

## The frame

Liquid models evolve from within (continuous, fluid, no
artefact, unauditable — yin). Authored weight patches evolve
from without (discrete, sealed, reversible — yang). Jacquard
is the harness where they meet: flow proposes, the record
disposes. This phase tests whether the yang pole is real
engineering or benchmark overfitting — and is built to be
able to say no.

## Target model (E1/E4/E6 narrow set)

Qwen/Qwen3-0.6B (bf16 safetensors, sha256-gated fetch through
the Thor download-governor; jobs wsp-qwen3-06b-*). Chosen:
smallest legible open causal LM in the paper's size class
(0.8B), standard architecture (28 layers, hidden 1024, tied
embeddings), resident nowhere — fetched as a COPY into
~/wsp-exp/models/ on the Thor. No resident model is ever
mutated in place; all patching happens on copies in
~/wsp-exp/work/.

## Batteries (built by the battery seat; never by the patcher)

Narrow set = multi-step arithmetic (word + direct forms),
programmatically generated with verified answers:
- diagnostic (80): patcher-visible, items + base outputs.
- validation (200): patcher sees per-category aggregates only.
- heldout (200): sibling distribution, disjoint lexical pools
  and template set B; patcher never sees items or scores
  until the coordinator scores a finished patch.
- E6 heldout is the SAME heldout split (teacher answers it in
  a separate session that never patches).
Forgetting batteries (patcher never sees any item):
- forget_instr (100): verifiable instruction-format checks.
- forget_fact (100): short factual QA from fixed fact tables.
- forget_prose (24 paragraphs): mean token NLL, no generation.
All splits deterministic (seeded generators); scoring is
greedy decoding, exact-answer extraction, code-scored —
no model judges any score that enters a verdict.

## Roles (seat separation is the held-out enforcement)

- Battery builder: a coder seat on the ORACLE (not the patcher).
- Battery reviewer: a coder seat on the ORIN — read-only audit
  of generator + split hygiene (leakage, template overlap,
  answer-verification bugs). A builder's own green is not proof.
- Patcher/teacher-diagnostician: a coder seat on the THOR
  (Kimi seat if its headless mode verifies; else roster order
  in the log). Works only in ~/wsp-exp/patcher/ with diagnostic
  data + validation aggregates.
- Teacher (E6 held-out answers): a strong-model session that
  never patches and never sees patch content — answers items
  only.
- Grader of record: the verified scoring scripts, run by the
  coordinator. Model graders do not score verdict quantities.
Pi seat on the Thor: unverified in fleet records — verify
on-box (binary, version, auth, drive mode) before relying on
it; record the finding either way.

## E1 (slice 41) — replication

Baseline the base model on all splits (coordinator-run).
Patcher receives: diagnostic items + base outputs on them,
per-category validation aggregates, architecture/config
facts. It diagnoses the failure and authors a SPARSE patch
(bounded: <=0.1% of scalar weights, exact edit list recorded)
as a re-runnable script applied to a copy. Coordinator scores
the patched copy on validation, heldout, and all forgetting
batteries. Question: does any effect survive held-out?

## E4 (slice 41) — is it engineering

The patcher must explain its patch (which weights, what they
compute, why these). Coordinator verifies by ablation:
(1) ablate claimed-critical edits -> effect should vanish;
(2) ablate a random equal-count set of the patch's edits
    (revert random edits of equal count) -> effect should
    persist; (3) restore -> effect should return. Ablation
runs are coordinator-executed from the patch script's edit
list, not by the patcher.

## E3 (slice 42) — the three poles

Same target failure: (a) fluid pole — best context/prompt
adaptation, no weight change (a strong prompt authored by
the patcher seat, frozen before scoring); (b) gradient pole —
LoRA fine-tune on the DIAGNOSTIC split only (same information
budget as the patcher), rank/al_lr fixed in advance, trained
on the Thor GPU; (c) yang pole — the E1 patch. All scored on
heldout + forgetting by the coordinator. Fourth column,
scored as strictly: AUDITABILITY — can each method produce
from its own artefacts a complete answer to "what changed,
why, on whose authority, how is it undone?"

## E5 (slice 42) — successive-task forgetting stress

Three successive narrow tasks (arithmetic = task 1; two more
generated families: date/interval arithmetic, unit
conversion) applied successively to the same base: patch
chain vs LoRA chain (each stage trained/patched only on its
own task's diagnostic data). After each stage, score ALL
tasks so far + forgetting batteries. Degradation curves for
both methods on one table.

## E2 + E6 (slice 43) — governed lifecycle and the loop

Sequencing decision (coordinator, recorded per steering):
E6's loop mechanics are proven FIRST on the arithmetic
narrow set (cleanest held-out control), running on the E2
rails built at the start of slice 43; E7/E8 then run as
application rounds of the proven loop. Rationale: E7 needs
a signal-chain joint inventory and E8 needs decision-record
battery curation — neither should gate the mechanics proof.

E2: one patch (the best available from E1/E6, adopted or
rejected — a rejected patch is a complete lifecycle) goes
through Jacquard end-to-end in a dedicated log in this
clone: patch artefact sealed by sha256 as a proposal;
battery evidence entered as senses; deployment discipline
offline eval -> shadow -> canary as staged entries; adoption
decided from the record via the decision queue (hash-bound);
then ROLLBACK executed and the base restored bit-for-bit
(sha256 equality of the weights file, recorded). Governance
cost measured: wall time + operator decisions, vs the
patch's own cost.

E6: the teacher-student patch loop on the narrow set.
Rounds: teacher diagnoses student failures per round from
round-battery aggregates + diagnostic items (fresh diagnostic
slice per round from the same generator family, disjoint
items), authors patch round r on top of the ADOPTED state;
each round is an E2 governed proposal (sealed, evidence as
senses, adopt/reject from the record). A round whose heldout
score regresses beyond noise is REJECTED and rolled back,
never compounded. If no natural regression occurs within
the round budget, one labelled rejection-path exercise round
(an over-aggressive patch, proposed as such) exercises the
path before the loop closes.
Headline per round: student-vs-teacher gap on HELDOUT
(teacher answered by the non-patching teacher session).
Stop conditions, stated in advance:
- round budget: 6 rounds;
- plateau: heldout gap closure < 2 points for 2 consecutive
  rounds -> stop, report plateau + fraction of gap closed;
- divergence: validation improves >= 5 points while heldout
  is flat/worse for 2 consecutive rounds -> name it
  overfitting, stop;
- forgetting guard: any round dropping a forgetting battery
  by > 5 points vs base is rejected regardless of gap.
Report: gap-closure curve + honest asymptote (parity /
plateau at stated fraction / overfit), and where the GAN
analogy holds/breaks (battery = judging function; teacher =
generator-of-students; no gradient anywhere; the difference
that matters: every round is a sealed, scored, reversible
commit — a distillation loop with a ledger).

## E7 (slice 43, application round 1) — signal-chain soft joint

Read-only inventory of SuperInstance/signal-chain: find a
workflow whose spine is hard/decided (decision-tree
structure) with ONE small judgement joint (classification
or weighting the tree cannot make). That joint's decisions
become a narrow set: battery = recorded/historical joint
decisions if the repo carries them, else a generated set
scored against the tree's own downstream outcomes (the
choice and its evidence standard recorded before round 1).
Loop target: teacher parity on held-out joint decisions.
Claim under test: hard spine stays auditable; only joints
are soft; each joint's coaching rounds are a governed record.

## E8 (slice 43, application round 2) — the custom decision model

Target: the advisor behind Jacquard's provider seam.
Curriculum = Jacquard's own record: recorded decisions from
the proof logs, booking-board decisions, gpu windows,
curated into a battery of decision items (context -> the
recorded decision). Held-out = LATER decisions (time split);
the patcher never sees them. A small decision model (the
E1 student architecture) is patched round by round (E6 loop)
toward the operator's weighting. Baselines to beat honestly:
stock advisor 10/11 agreement (Phase 2/3 experiment) and the
shadow trial's 88% (46/52). TWO scores, reported separately:
(a) agreement-with-the-operator (preference fidelity);
(b) agreement-with-correctness on the subset where the
record itself shows the operator/incumbent was wrong (the
shadow trial's 3 incumbent-wrong cases and any like them) —
learning the operator's mistakes as faithfully as their
judgement is a finding, not a success. Constitutional line,
stated in the E8 record: the custom model remains a SENSE
behind the provider seam; the kernel and the record still
gate. It advises; it never decides.

## Honesty gates

If E1 shows no held-out effect beyond noise, slices 42-43
re-scope to the negative per the brief: comparisons run
with the null as the finding, the governed lifecycle is
demonstrated on the best available patch regardless of
score, E6 runs (a loop is the stronger test) with
expectations re-stated in the log before round 1, and the
findings document leads with the negative.
