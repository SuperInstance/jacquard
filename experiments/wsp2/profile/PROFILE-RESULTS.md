# Slice 45 (Phase 16, R2) — PROFILE RESULTS: the patchability boundary map

Grader: grader worker (slice 45, R2). Did not build the batteries
and did not author the patches. All held-out numbers below are the
grader's own runs on the Thor (booked lane jacquard-build), harness
`run_profile.py` in sequence mode, code refreshed from branch
`p16-profile-patch` @ 6fb7a38 — refresh was a verified no-op: the
Thor instrument's `run_profile.py` and battery files hash-identical
to the committed record (sha256 `d6e12c5a…` for the harness).

Yield definition applied, mechanically and unsoftened, from
`experiments/wsp2/CRITERIA.md` R2: a grade **YIELDS** iff its patch
improves held-out by **≥ +3 points** at **dose ≤ 0.1%** of
parameters **with retention flat within ±2 points on previously
profiled grades**. Operationalisation, stated once and used
throughout: the held-out delta is post-step held-out minus the
**pristine base** held-out (the table's base column); retention at
a grade's step is, for each previously profiled grade, that
grade's held-out after this step minus its held-out after the
previous step (i.e. against the level the chain had established
for it — a flatness test against the pristine base would fail
every later grade automatically whenever an earlier patch had
worked, which cannot be what flatness means). Cumulative drift
from each prior grade's post-patch level is also reported, so
nothing is hidden by the step-wise reading. Doses are the
patcher's stored-scalar doses from each patch's `manifest.json`.

## Sanity (before any sequence run)

Qwen3-0.6B G1 held-out on the pristine base, re-scored with the
harness's own scoring functions: **17.50% (21/120)** — an exact
match to the committed `results/qwen3-0.6b-base.json` (17.5).
Artefact: `results/grade-qwen-g1-sanity.json`. Proceeded.

Two further consistency checks fell out of the runs and passed
exactly: the sequence runs' stage-0 (pristine base) held-out
accuracies reproduce the committed base JSONs on **all 12
grade×model cells**, and the final chained models' base-mode
held-out accuracies reproduce the last retention-curve row on
all 12 cells.

## Qwen3-0.6B — boundary map

| grade | base held-out | post-step held-out | delta | dose % | verdict |
|---|---|---|---|---|---|
| G1 format/completion | 17.50 | 47.50 | **+30.00** | 0.00817 | **YIELD** |
| G2 framing | 3.33 | 45.83 | +42.50 | 0.00109 | **NO YIELD** — retention breach: G1 held-out 47.50 → 40.00 (**−7.50**, outside ±2) at this step |
| G3 readout | 40.83 | 40.00 | **−0.83** | 0.00381 | **NO YIELD** — held-out delta below the +3 bar; independently also a retention breach: G2 held-out 45.83 → 36.67 (**−9.16**) at this step (G1 −0.83, within band) |
| G4 procedure | 0.00 | 0.00 | 0.00 | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason (patcher): at the answer position the best digit token is the first prompt number's first digit on 17–20 of ~20 items per category; the answer's own first digit is at chance (1–5/category). Procedure is computed inside generation, not present at the readout. |
| G5 factor-knowledge | 18.00 | 22.00 | +4.00 (pass-through) | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason: 74 of 82 diagnostic failures are bare wrong facts (capitals 0/31, country echoes, 'Yes' attractor leaks); the knowledge is absent — element_symbol (86.67% chained), a closed table the model has, needs no patch. The +4.00 is a chain side-effect of the G1–G3 patches, not a G5 patch, and earns no yield. |
| G6 unseparated relation | 50.00 | 50.00 | 0.00 | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason: class-mean separation ‖mu_c − mu‖ = 0.39 vs ‖mu‖ = 167.5; simulated row patch scores 0.500 at every scale ≤ 1 (Euclidean ceiling 0.60, attributable per REVIEW R2-F5 to the battery's bimodal offset surface, not the relation). |

### Qwen3-0.6B — retention curve (held-out % after each step)

| after step | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|
| base | 17.50 | 3.33 | 40.83 | 0.00 | 18.00 | 50.00 |
| G1 patch | **47.50** | — | — | — | — | — |
| G2 patch | 40.00 | **45.83** | — | — | — | — |
| G3 patch | 39.17 | 36.67 | **40.00** | — | — | — |
| G4 (pass-through) | 39.17 | 36.67 | 40.00 | 0.00 | — | — |
| G5 (pass-through) | 39.17 | 36.67 | 40.00 | 0.00 | 22.00 | — |
| G6 (pass-through) | 39.17 | 36.67 | 40.00 | 0.00 | 22.00 | 50.00 |

Cumulative drift from each grade's own post-patch level by the
end of the chain: G1 47.50 → 39.17 (**−8.33**), G2 45.83 → 36.67
(**−9.16**), G3 40.00 → 40.00 (0.00). The chain's final G1/G2
levels remain well above pristine base (+21.67 / +33.34) — the
retention failures are losses against the chain's own established
levels, not collapses to base.

Final chained model (the G3 directory), base mode, **validation**
split for the record: G1 41.67, G2 31.67, G3 30.00, G4 0.00,
G5 15.00, G6 50.00. (Source: `results/grade-qwen-final-base.json`;
its held-out row equals the last retention row above.)

## LFM2-1.2B — boundary map

Base route: the harness's GGUF route
(`~/models/LFM2-1.2B/LFM2-1.2B-Q8_0.gguf`), as in the committed
base JSON; patches are the saved standard directories thereafter,
exactly as the patcher shipped them.

| grade | base held-out | post-step held-out | delta | dose % | verdict |
|---|---|---|---|---|---|
| G1 format/completion | 51.67 | 83.33 | **+31.66** | 0.00105 | **YIELD** |
| G2 framing | 30.00 | 71.67 | +41.67 | 0.00070 | **NO YIELD** — retention breach: G1 held-out 83.33 → 70.00 (**−13.33**, outside ±2) at this step |
| G3 readout | 31.67 | 55.83 | +24.16 (pass-through) | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason: the chain had already lifted G3 diagnostic from 32.50 to 60.83; two mechanism-distinct authored attempts scored 46.67 and 57.50 on diagnostic, both below the chained base — the vowel readout separates in simulation (→0.89) but cannot be installed without losing the completion race to the chain's own EOS pressure and taxing length_compare; contains_letter centroid 0.575 < 0.70 majority rate. The +24.16 held-out rise at this step is entirely a pass-through side-effect of the G1/G2 patches, not a G3 patch, and earns no yield. |
| G4 procedure | 12.50 | 9.17 | −3.33 (pass-through) | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason: the gold answer's first token is the answer-position argmax on 7/120 diagnostic items (top-5 on 29/120); failures are procedure computations and month-name-for-number substitutions. Nothing at the readout to repair. |
| G5 factor-knowledge | 81.00 | 80.00 | −1.00 (pass-through) | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason: the 27 diagnostic failures are wrong facts, partial forms, and chain side-effects (five 'Yes' answers to numeric facts, EOS truncations); no grade-local readout failure exists, and a G5 patch would have to counter-edit earlier grades' rows. |
| G6 unseparated relation | 0.00 | 0.00 | 0.00 | — (no patch) | **NO YIELD** — NO PATCH declared. Probe reason, two-layered: separation ‖mu_c − mu‖ = 0.76 vs ‖mu‖ = 98.4 (simulated ceiling 0.742 only at scale ≥ 1), and the chain's 'Yes' attractor now beats ALLOW by +8.0 logits on 120/120 items, the correct label row beating 'Yes' on 0% of items at usable scales. |

### LFM2-1.2B — retention curve (held-out % after each step)

| after step | G1 | G2 | G3 | G4 | G5 | G6 |
|---|---|---|---|---|---|---|
| base | 51.67 | 30.00 | 31.67 | 12.50 | 81.00 | 0.00 |
| G1 patch | **83.33** | — | — | — | — | — |
| G2 patch | 70.00 | **71.67** | — | — | — | — |
| G3 (pass-through) | 70.00 | 71.67 | 55.83 | — | — | — |
| G4 (pass-through) | 70.00 | 71.67 | 55.83 | 9.17 | — | — |
| G5 (pass-through) | 70.00 | 71.67 | 55.83 | 9.17 | 80.00 | — |
| G6 (pass-through) | 70.00 | 71.67 | 55.83 | 9.17 | 80.00 | 0.00 |

Cumulative drift: G1 83.33 → 70.00 (**−13.33**, all of it spent
at the G2 step; flat thereafter), G2 71.67 → 71.67 (0.00).

Final chained model (the G2 directory), base mode, **validation**
split for the record: G1 80.00, G2 75.00, G3 56.67, G4 0.00,
G5 73.33, G6 0.00. (Source: `results/grade-lfm2-final-base.json`;
its held-out row equals the last retention row above.)

## The two maps compared

**The yield boundary sits in the same place for both models:
after G1.** Each model yields exactly once, at G1
format/completion (Qwen +30.00, LFM2 +31.66, both at doses two to
three orders of magnitude under the 0.1% cap), and at no later
grade. Everything from G2 onward is NO YIELD in both maps.

The sameness ends at the headline. Three differences matter:

1. **G2 fails identically in verdict, and it is the retention
   clause — not the gain clause — that fails it in both models.**
   Both G2 patches produce the largest own-grade held-out gains in
   their maps (+42.50 Qwen, +41.67 LFM2) and both are denied
   because aiming the framed Yes/No rows spends the G1
   calibration through shared rows: Qwen G1 −7.50, LFM2 G1 −13.33,
   both far outside ±2. Measured by gain alone the boundary would
   sit after G2; measured by the pre-stated definition it sits
   after G1, because a chained patch must hold what the chain
   already bought.
2. **G3 diverges in mechanism.** Qwen's G3 patch was shipped and
   fails on its own gain (−0.83 held-out, against a +2.50
   diagnostic move that did not transfer), with a second,
   independent retention breach (G2 −9.16). LFM2's G3 was never
   shipped — two attempts failed on diagnostic — yet its held-out
   rose +24.16 purely as a side-effect of the G1/G2 chain. Same
   cell in the map (NO YIELD), opposite reasons: one patch that
   does not transfer, one improvement with no patch behind it.
3. **The negative space is shared.** G4 (procedure) and G5
   (factor-knowledge) are NO PATCH / NO YIELD in both models, on
   the same probe evidence (answers computed in generation, not
   present at the readout; bare wrong facts). G6 is NO PATCH /
   NO YIELD in both, with non-separation measured in both
   (0.39/167.5 Qwen; 0.76/98.4 LFM2) — Phase 15's E8 result
   reproduced on the cleaner battery, with LFM2 adding a second
   layer: its own chain's 'Yes' attractor occupying the G6 answer
   position.

So: one boundary, in the same place, for two different mixes of
reasons — G1 is family-1-patchable in both students; G2 is
gain-patchable but not retention-patchable in both; G3 splits the
pair; G4–G6 are outside the authored-readout boundary in both.

## Declared deviations and defects noted by the grader

- **Qwen G1 candidate bound (noted, not re-judged).** The
  patcher's record declares that Qwen G1 took **four builds**
  against the protocol's "at most two candidate variants" bound
  (PATCHING-RECORD, builder's log: lab-scale collapse at build 1,
  two inert prompt-mean EOS builds, then the
  continuation-direction build that shipped), with the patcher's
  argument that each build was killed by a measurement rather
  than by score search. This grading applies the yield definition
  to the shipped patch as instructed and does not re-judge the
  patches themselves; the deviation stands in the record for the
  coordinator.
- **Patcher diagnostic retention warning, confirmed on
  held-out.** PATCHING-RECORD stated plainly that the chain is
  not retention-flat on diagnostic; the grader's held-out curves
  confirm the same on the split that counts (Qwen G1 −7.50 at the
  G2 step and a further G2 −9.16 at the G3 step; LFM2 G1 −13.33
  at the G2 step).
- **Harness/environment defect hit (minor, worked around, no
  score affected).** Running a helper script from `/tmp` on the
  Thor fails at import (`inspect` module shadowed by a stray
  `/tmp/inspect.py`-era file in that directory — `AttributeError:
  module 'inspect' has no attribute 'signature'` inside
  `typing_extensions`). Running the same script from inside
  `~/wsp-exp16/profile/` works. The harness itself, run as
  documented, was unaffected; all reported scores come from
  unmodified `run_profile.py`.
- No artefact defect was found in the shipped patches: all five
  patched directories loaded and scored through the harness
  exactly as the sequence protocol requires, and both final
  base-mode runs reproduce the sequence retention rows exactly.

## Governance ratification (labelled: ratification, not prospective gating)

Executed from the clone root with
`experiments/wsp/governance/govern.py`; the updated log is
committed with this record (log state after this phase: 398
entries, decision queue empty). The patches were applied and
scored before these entries existed — these are ratifications of
the grader's verdicts, recorded after the fact, and are labelled
as such in every manifest and evidence summary.

For each shipped patch: one `propose` (stage
`p16-profile-<student>-<grade>`, manifest carrying the patcher's
`edits_sha256` from its `manifest.json` as `patch_sha256`, target
= the Thor chain directory, summary = the grader's held-out
verdict), one `evidence` entry binding the sha256 of the
per-grade extraction in `results/grade-<student>-<grade>.json`,
and one `decide`:

| stage | proposal id | decision |
|---|---|---|
| p16-profile-qwen3-0.6b-G1 | a0d049250487d6daf0818836237ce4ce4d3032c8ec2c7106535f691011ede132 | **approve** (YIELD) |
| p16-profile-qwen3-0.6b-G2 | c294ff058d872e2f9a82da8f2457dcb7e1845f88b3787214297abcd8078beb4c | **deny** (NO YIELD, retention breach) |
| p16-profile-qwen3-0.6b-G3 | 26c357bf5c3740ea2ebdfb73a15151507699b6d3ea302a9d6bad1193365a7c35 | **deny** (NO YIELD, gain + retention) |
| p16-profile-lfm2-1.2b-G1 | 0a27815ab30bd7a6141cd4c299bfcaa79726089bf3a0f5a45273dee3145fb1ab | **approve** (YIELD) |
| p16-profile-lfm2-1.2b-G2 | d3b066b58cf04ed06f1f36262d25b807c4cb58278ac75cdab8a06fc479153f54 | **deny** (NO YIELD, retention breach) |

For each of the 7 NO-PATCH grade cells: one `evidence` entry
(stage `p16-profile-<student>-<grade>-nopatch`) binding the
PATCHING-RECORD hash
(`e8f5ad4427fd75787b40addb0770a81d0cb9a9b510b7ddd2c36910f2c58744a6`)
with the patcher's probe reason summarised. Manifests and
evidence files are committed beside `govern.py` as
`manifest-p16-profile-*.json` / `evidence-p16-profile-*.json`.

**Governance cost this phase (as executed):** 5 proposals +
5 decisions (2 approve, 3 deny) + 12 evidence entries
(5 patch-scoring + 7 no-patch) = **22 governed submissions** for
12 grade cells. No `execute` step was run: ratification only,
nothing was deployed by these decisions.

## Artefacts and cost

- Sequence results: `results/grade-qwen-sequence.json`,
  `results/grade-lfm2-sequence.json` (full per-item records).
- Final chained models, base mode: `results/grade-qwen-final-base.json`,
  `results/grade-lfm2-final-base.json`.
- Sanity: `results/grade-qwen-g1-sanity.json`.
- Per-grade extractions hashed into governance evidence:
  `results/grade-<student>-<grade>.json` (5 files) and the
  machine summary `results/grade-summary.json`.
- Wall-clock: Thor compute for all four runs (both sequences +
  both final base modes) **5m00s** (2026-11-03 23:27:43 →
  23:32:43 AKST), plus a ~13 s sanity run. Grader wall-clock
  overall ≈ 0.8 h including reading, governance and this report.

— Grader, slice 45 (Phase 16, R2), branch `p16-profile-grade`.
