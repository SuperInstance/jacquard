# Phase 17, W2 — battery for the nearest-miss joint

Joint (nearest miss, per W2-INVENTORY.md): **gpu-queue
job-shape classification** — classify a Thor gpu-queue job by
its foundry archetype from its recorded job text.

## Spine, incumbent, classes

- Hard spine: the Thor `gpuq` daemon (`~/gpu-queue/daemon.py`:
  successor rule enforced at dispatch, start-failure retry
  then halt, feeder materialisation by rotation), driving
  `~/foundry/mint.py family --archetype …` jobs. The Jacquard
  bridge (slices 22/25) sat over the same queue for governed
  submissions; its record is the judgement-shaped one counted
  in the inventory (17 submissions — below the bar).
- Incumbent: the spine's own recorded handling. For this
  class the archetype is chosen by the daemon's feeder
  rotation (or supplied in a finite job's cmd) and written
  into the job's name and cmd. The incumbent scorer
  (`w2/score_incumbent.py`) therefore predicts by parsing
  `--archetype` from the item's recorded text (name-template
  fallback) — scored from the record alone, no model.
- Class definitions (the only >= 500 balanced classes in the
  record; labels derived from the recorded `--archetype`
  field of `queue.json`, no human labelling):
  - `fishing_boat` — mint family job for the fishing_boat archetype
  - `harbor_house` — mint family job for the harbor_house archetype
  - `pier` — mint family job for the pier archetype
  - `spruce` — mint family job for the spruce archetype
- Item text (`message`): `<job name>\n<job cmd>`, exactly as
  recorded. Schema mirrors Phase 15 E7: {id, split, label,
  subtype (= recorded kind), boundary (= kind != feeder),
  message} + provenance {job_id, added, kind}.
- Excluded, counted: the 14 non-foundry finite jobs (jacquard
  bench/sentinel/net/held/stranger) carry no archetype; they
  are the finite-record gap discussed in the inventory.

## Split (temporal, per CRITERIA.md §W2)

Source: copy of Thor `~/gpu-queue/queue.json` (1,651 jobs),
taken 2026-11-04 to Thor `~/wsp-exp17/w2/raw/`; resident files
not mutated. Foundry jobs (archetype present): 1,637, sorted
by (`added`, id).

| split | n | range (added) | per class | file | sha256 |
|---|---|---|---|---|---|
| diagnostic | 1,145 | 2026-10-27T23:20-0800 → 2026-10-28T12:30-0800 | fishing_boat 287, harbor_house 287, pier 286, spruce 285 | `w2/battery/diagnostic.jsonl` | e551c9bb1bcfb990b582f3e23f19406a75918060fb46ead8f64069dc4ba4ffc6 |
| held-out (sealed) | 492 | 2026-10-28T12:31-0800 → 2026-10-28T18:40-0800 | 123 / 123 / 123 / 123 | `w2/battery/heldout.sealed.jsonl` | 2a669782ce7e42d03e854057415e0bd490dd35d24a7fd3f94beacafd80f95298 |

Held-out is sealed in the Phase 15/16 sense: committed as
`heldout.sealed.jsonl` with its sha256 recorded here and in
`w2/battery/split.json`; its contents are not reproduced in
any other W2 document, and the patcher (if a round is ever
chartered) receives diagnostic + these class definitions
only. Diagnostic contains exactly 2 finite jobs (job-1,
job-2); all other items in both splits are feeder jobs — that
composition is the record's, not a sampling choice.

Builder: `w2/build_battery.py` (stdlib, deterministic;
re-running it on the same queue.json copy reproduces both
files byte-identically).

## Leakage checks (the E7 checks, run expecting trouble)

From `w2/battery/leakage.json`, computed across the split
boundary by the builder:

- exact duplicate messages across splits: **0** (seed numbers
  differ, so no two messages are byte-identical);
- held-out items whose digit-normalised template already
  appears in diagnostic: **492 / 492 (100%)**;
- cross-split token-Jaccard: max **0.8947**, and the mean
  nearest-neighbour Jaccard is also **0.8947** — every
  held-out item's nearest diagnostic neighbour sits at the
  same high similarity (four templates, rotating);
- distinct digit-normalised cmd templates in the whole
  battery: **4**.

Verdict: this is the reskin structure Phase 15's verifier
caught at Jaccard 0.92 — held-out here is diagnostic with the
seed numbers advanced. Any score on it measures template
recognition, not transfer. Stated as a property of the
record, not hidden by the (passing) exact-duplicate check.

## Baselines (measured 2026-11-04, Thor)

Incumbent scorer (`w2/score_incumbent.py`, record alone):

| split | accuracy | per class |
|---|---|---|
| diagnostic | **1.0000** (1,145/1,145) | all four classes 1.000 |
| held-out | **1.0000** (492/492) | all four classes 1.000 (123 each) |

Full per-item results: `w2/results_incumbent_diag.json`,
`w2/results_incumbent_held.json`. The perfection is
structural, not a triumph: gold and prediction are the same
recorded field (see the scorer's docstring). It means the
CRITERIA shadow bar (held-out >= incumbent + 10, no class
traded away) is **unreachable by construction** for this
joint — a specialist can at best tie a lookup.

Student task (Phase 15/16 shape, for the patcher if chartered):
fixed prompt over Qwen3-0.6B (bench copy, Thor
`~/wsp-exp/models/Qwen3-0.6B`) —

> Classify the job as fishing_boat, harbor_house, pier, or
> spruce. Answer with just the label.
>
> \<job name + cmd\>

Scorer: `w2/score_student.py` (adapted from E7's
`score_joint.py`, same conventions: chat template with
`enable_thinking=False` as a loud error, EOS union, bf16,
greedy, batch 16, max 8 new tokens, first word-boundary label
occurrence wins; selftest PASS, 9 cases).

Zero-shot student, **diagnostic split only** (held-out never
run against the student by W2):

| split | accuracy | per class | wall time |
|---|---|---|---|
| diagnostic | **1.0000** (1,145/1,145) | all four classes 1.000 | 19.4 s, one run |

Full output: `w2/results_student_diag.json`.

## What this battery proves, and what it is for

Incumbent 100%, zero-shot student 100%, held-out = reskins:
there is no judgement in this joint for a patch to install —
the representation does not need a readout because the answer
is printed on the input. That is the measured content of the
nearest-miss verdict in W2-INVENTORY.md. The battery and both
scorers are nevertheless complete and runnable, and they are
the ready-made harness for the joint that *would* clear the
bar — bridge allow/deny/hold over governed submissions —
the day its recorded traffic reaches 500 events: swap the
label derivation in `build_battery.py` (recorded outcome
field of the bridge journal) and every other piece stands.

No patch was authored by W2 (charter: a separate patcher,
diagnostic split only). The governance log was not touched.
