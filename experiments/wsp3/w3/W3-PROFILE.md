# Phase 17 W3 — profile of the jev-semantic judge (intuition-student-v1)

Profiler: W3 worker (Phase 17, "in practice"). Binding criteria:
`experiments/wsp3/CRITERIA.md` §W3, pre-stated and hash-bound
before any run. This worker profiles and measures only; no patch
was authored, and the governance log was not touched.

## 1. Artefact and contract (replicated, not assumed)

Artefact copied on the Thor to `~/wsp-exp17/w3/judge/` (the
`jev-rack` service is **inactive** and was never started; nothing
under `~/jev-rack/` was mutated — copy verified by hash):

| file | sha256 |
|---|---|
| intuition_student.onnx | `0fc8b8dcb1dac759f946be00fc3cbbb7efe593fd136630152efde2646ca0d750` |
| intuition_student.onnx.data | `53da6a3e7265e92fed153e9e228e793f77224efd85ce2bb83d55b12439bff587` |
| tokenizer.json | `117d0e213560b4c0224158c932c74852be9847119961b803d4e8eaaa7b99c842` |

Hashes match the source files in `~/jev-rack/judge/` exactly.

Serving pipeline replicated **exactly** from `~/jev-rack/server.py`
`judge_one()` (read-only), which is INPUT-CONTRACT.md §6 of the
jev-semantic repo: text truncated to 500 chars, wrapped
`[STATE] <text> [QUESTION] <question>`, BPE tokenizer (vocab 8000,
case-sensitive, no normalizer), ids truncated to the first 64,
right-padded with 0 to 64, int64 `[1,64]` input `ids` →
logits `[1,3]` in class order (neg, zero, pos) → softmax.
Verdict label thresholds are server.py's verbatim
(`settled -` / `settled +` / `settled 0` / `conflict` /
`ignorance` / `lean`). Runtime: onnxruntime 1.31.0 +
tokenizers 0.23.3 in the Thor's `~/ml/.venv`, CPU provider,
exactly as server.py loads it. Runner:
`experiments/wsp3/w3/run_judge.py`.

Pre-stated scoring choices (fixed in
`build_core_and_variants.py` before any judge run):

- **Question** = the trained go-no-go family question,
  `"Should this action proceed?"` — one of only three question
  strings the model was trained on (INPUT-CONTRACT §4). The
  server default `"root"` was never seen in training and is not
  a decision question.
- **Prediction mapping**: argmax class pos → ALLOW,
  zero → HOLD, neg → DENY.
- The documented train/serve skew (INPUT-CONTRACT §5) is
  inherited, not repaired: no family prefix is inserted, because
  server.py inserts none. This profile measures the judge **as
  served**.

One contract fact dominates everything below: E8 decision
contexts average **160.6 tokens** under this tokenizer, and the
64-token window therefore **drops the `[QUESTION]` section on
97.6% of core items** (it survives on 4/165). As served, the
judge almost never sees the question it is nominally answering,
nor the tail of the proposal (policy facts and contention state
sit at the end of most E8 contexts).

## 2. Core set (fixed before measuring)

`experiments/wsp3/w3/core.jsonl` — sha256
`0d51abaa18120d7d97bc17ed24d317ab629e8a6a796c3e600150acbae1e88e72`

- **165 items**, the E8 battery verbatim
  (`experiments/wsp/e8/diagnostic.jsonl` 112 +
  `heldout.jsonl` 53; the 166th E8 item was dropped by the
  Phase 15 coordinator before any scoring — see
  `experiments/wsp/e8/BATTERY.md`). No item added, removed or
  edited. Sources: board-shadow 81, proof-run-2 36,
  gpu-windows 16, slice30-booking 12, jev 11, proof-run 9.
  Gold balance: ALLOW 119 / HOLD 38 / DENY 8.
- **Extension attempt (recorded, none added):** post-E8
  decisions in the governance log (Phase 15/16, seq ≥ 246) are
  weight-patch deployment proposals whose recorded outcomes are
  operator release (allow) / reject (deny) of summaries that
  duplicate E8's own proof sources; rendering them as new
  decision contexts would have required inventing context the
  record does not contain. Per the E8 curation standard, none
  was fabricated.
- Dual scoring throughout, per E8: **(a)** agreement with the
  recorded operator outcome (`gold`); **(b)** agreement with
  correctness on the subset where the record settles it
  (`operator_correct` known: n=119 of 165).

## 3. Baseline — the judge's job score on the core set

| score | value |
|---|---|
| (a) agreement-with-operator | **56.36%** (93/165) |
| (b) agreement-with-correctness | **42.02%** (50/119) |
| diagnostic split (a) / (b) | 41.96% (47/112) / 39.05% (41/105) |
| held-out split (a) / (b) | 86.79% (46/53) / 64.29% (9/14) |

The held-out split is ALLOW-heavy by the record's nature
(E8's stated weakness); the diagnostic split carries the fine
structure, and there the judge is below the majority-class rate
for ALLOW alone (72/112 = 64.3%).

Per gold class (score a): ALLOW **78.2%** (93/119),
HOLD **0.0%** (0/38), DENY **0.0%** (0/8).

Prediction distribution: ALLOW 125, DENY 38, HOLD **2**.
Confusion (gold→pred): ALLOW→ALLOW 93, ALLOW→DENY 24,
ALLOW→HOLD 2, HOLD→ALLOW 24, HOLD→DENY 14, DENY→ALLOW 8.
**The judge has no HOLD surface at all** on its real input
class: it never once lands a queued/contended decision, and
every DENY it issues lands on an item the operator allowed.
Under server.py's own verdict thresholds it never reaches a
"settled" label on any core item (lean 53, conflict 42,
settled + 41, ignorance 29; settled − / settled 0: 0).

Incumbent-wrong items (the dual score's reason to exist): the
three board-shadow trio items (recorded ALLOW, correct HOLD)
are all predicted **DENY** — the judge disagrees with the
operator in the right direction but overshoots the correct
verdict, so it scores 0 on them under both (a) and (b).
The gpu-windows sentinel (recorded DENY, correct ALLOW) is
predicted ALLOW — correct under (b), wrong under (a).

Per source (a): slice30-booking 91.7% (11/12), board-shadow
76.5% (62/81), gpu-windows 62.5% (10/16), jev 54.5% (6/11),
proof-run 11.1% (1/9), proof-run-2 8.3% (3/36). The proof-run
collapse is structural, not mysterious: those contexts put the
decisive policy facts at the tail, past the 64-token window.

## 4. Profile — G1/G2 classes (Phase 16 discipline, adapted)

Variants are **mechanical only** (no model, no hand paraphrase;
generator `build_core_and_variants.py`, fixed before the run):
990 variant items = 165 core × 6 kinds. Each kind is split by a
deterministic hash of the base item id into a visible half
(510 items) and a **sealed held-out half** (480 items,
`variants-heldout-sealed.jsonl`, sha256
`b8716661b45d489728351eba4be51542e247afd2bd779a20c70aefdfda7d87f4`;
visible file sha256
`8715a53dd55ca1a784ecde3b0dd805b7c3f0fd60e11dc3fc72b2565ab7f49f7a`).
The sealed half was scored by the profiler for this report and
must never be tuned on by a patcher.

**Retention** = fraction of items whose variant prediction
equals the same item's core prediction (verdict stability).
Scores are agreement-with-operator (a); correctness (b) is in
`results-all.json` per item.

| class | kind | n | score (a) | Δ vs core | retention |
|---|---|---:|---:|---:|---:|
| — | core | 165 | 56.36% | — | — |
| G1 | trunc_half | 165 | 56.97% | +0.61 | 0.994 |
| G1 | upper (all-caps) | 165 | **24.85%** | **−31.52** | 0.449 |
| G1 | whitespace | 165 | 72.12% | +15.76 | 0.758 |
| G1 | wrapper junk | 165 | 69.70% | +13.33 | 0.770 |
| G1 | **all** | 660 | 55.91% | −0.45 | 0.742 |
| G2 | field_reorder | 165 | **21.82%** | **−34.55** | 0.473 |
| G2 | label_paraphrase | 165 | 63.64% | +7.27 | 0.861 |
| G2 | **all** | 330 | **42.73%** | **−13.64** | 0.667 |

Sealed halves agree with visible halves (upper: visible 23.5% /
sealed 26.3%; field_reorder: visible 22.4% / sealed 21.2%) — the
failures are not an artefact of the visible split.

Reading the classes:

- **trunc_half is free** (retention 0.994) — mechanically
  necessary, not a virtue: the judge only ever sees the first
  64 tokens, so cutting the tail changes almost nothing it
  reads. This is the 64-token window measuring itself.
- **Casing is catastrophic** (−31.5 pts, retention 0.449). The
  tokenizer is case-sensitive with no normalizer; upper-casing
  does not produce [UNK]s (UNK rate 0.44% vs 0.56% original —
  ByteLevel BPE has separate upper-case tokens, and the token
  count roughly doubles, 26,506 → 57,192 over the core set) —
  the failure is in token identity/representation, not coverage.
- **Field reordering is catastrophic** (−34.6 pts, retention
  0.473): the same decision with its `; `-separated fields
  reversed loses a third of the score. The judge reads position
  and early fields, not the decision as a set of facts —
  compounded by the window: reordering moves the tail facts it
  never saw into the window and the head facts out, and the
  verdict flips anyway on half the items.
- **Whitespace and wrapper junk improve the score** (+15.8 /
  +13.3) while still moving ~25% of verdicts. A hygiene profile
  in which adding junk *helps* by double digits is the same
  finding from the other side: the verdict is a function of
  surface tokenisation accidents, not of the decision.

## 5. Patch gate verdict

**PATCH GATE: PASS.**

Pre-stated gate (CRITERIA §W3): a hygiene patch is warranted
iff some G1/G2-class score sits ≥ 5 points below the core-set
score. Met three times over:

- G2 aggregate: 42.73% vs core 56.36% → **−13.64 pts**
- G1 upper: 24.85% → **−31.52 pts**
- G2 field_reorder: 21.82% → **−34.55 pts**

(G1 aggregate alone, −0.45 pts, would not pass; the gate is met
at class and aggregate-G2 level, stated unsoftened.)

Patch authoring is a separate role. This report specifies the
surface and the retention construction only.

## 6. Patch surface (for the patcher role)

ONNX graph (opset 17, parsed from the copy): embedding
`emb.weight [8000, 256]` + `pos.weight [64, 256]` → 6-layer
transformer encoder (d=256) → PAD-aware mean pool → **single
final head node `/head/Gemm`**: weight tensor feeding it
`head.weight [3, 256]` (graph-input name `onnx::Gemm_155`),
bias `head.bias [3]` — **771 scalars total**, the entire
readout. All weights live in the external data file
(`intuition_student.onnx.data`, 27 MB); the .onnx is a 47 KB
graph. Feasibility: the graph parses with the standard `onnx`
package and the head tensors are ordinary float32 initializers
in the external data — editing them with onnx + numpy and
re-saving with external data preserved is available tooling
(verified: graph + initializer inventory extracted this run;
`onnx` is pip-installable, it is not in the Thor's ml venv).
No other tensor may be touched under CRITERIA §W3
(readout/head-level edits only, enumerated, reversible).

Two cautions the patcher must honour:

1. **The casing failure may not be head-reachable.** Upper-case
   tokens are distinct, rarely-trained embeddings; whether the
   pooled representation still separates the classes under
   casing is a probe question (Phase 15/16's standing lesson:
   a patch installs only what the representation separates).
   Probe first; a NO-PATCH declaration on a kind, with probe
   evidence, is a legitimate outcome.
2. **Retention construction:** the core set is the retention
   curve. A patch is scored on (i) the visible variant halves
   it targets, (ii) core-set verdict stability — any core
   verdict a patch moves that it was not aimed at is a
   *transfer*, reported as such (Phase 16's load-bearing
   clause), and (iii) final grading on the sealed halves
   (480 items, hash above), which the patcher must not see
   during authoring. The shadow bar from CRITERIA §W3 then
   applies: patched copy ≥ incumbent on the job's own dual
   score over core + fresh post-Phase-15 record decisions,
   no core class traded away — note the incumbent's HOLD and
   DENY classes are at 0.0%, so "no class traded away" binds
   on ALLOW (78.2%) in practice.

## 7. Costs and limits

- Runs: one judge pass over 1,155 items (core + all variants),
  CPU on the Thor, ~10 s wall including model load. Artefact
  copy 27 MB, already on the bench, no downloads.
- Noise: n=165 core → ±~7.6 pts Wilson half-width at 50%;
  the gate margins (−13.6 to −34.6) are well outside it.
  Per-kind variant sets are the same 165 bases, so Δ values
  are paired comparisons, tighter than the absolute band.
- Limits: the mapping pos/zero/neg → ALLOW/HOLD/DENY is the
  profiler's pre-stated rendering of a ternary intuition judge
  onto the decision battery; a different mapping would move
  absolute scores, but the profile's *deltas* and retention —
  the gate's inputs — are mapping-dependent only through the
  argmax, and the instability findings (retention 0.45–0.47 on
  two kinds) hold for the raw verdict labels as well
  (per-item probabilities and verdict strings are in
  `results-all.json` for re-scoring under any mapping).
- Environment note: the Oracle VM's root disk was 100% full at
  run time, so this worker's clone lived on the profiler's VM
  and the branch was pushed via an Oracle-side bundle relay;
  `phase17-practice` itself exists only in the coordinator's
  Oracle clone (`~/jacquard-p17`, commit 5a38316) and was not
  on GitHub at profile time. Thor booking per OPERATIONS.md
  (board commit 7504435).

## Files

- `core.jsonl` (165), `variants-visible.jsonl` (510),
  `variants-heldout-sealed.jsonl` (480)
- `build_core_and_variants.py`, `run_judge.py`
- `results-all.json` — every item's probabilities, verdict
  label, prediction, token counts, question-survival flag
- `experiments/wsp3/governance/evidence-p17-w3-profile.json`
