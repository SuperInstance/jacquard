# Patchability profile

A profiling instrument for small language models. It measures
*where* a model's failures sit on the boundary between behaviour
and capability, by scoring it on six task grades ordered by
failure type:

| grade | failure type | what the tasks look like |
|---|---|---|
| G1 | format / completion | copy a word, answer a trivial sum, give the last word of a sentence — the knowledge is trivial; only the output contract can fail |
| G2 | framing | the same level of content under framing that misleads: negated questions, false claims to judge, distractor facts, quoted questions |
| G3 | readout | surface properties the representation plainly carries — first letter vowel or consonant, word length, letter containment, word case, sentiment of an unambiguous sentence |
| G4 | procedure | multi-step procedures executed reliably: date arithmetic (days between dates, weekday offsets, whole months), week decomposition, chained arithmetic |
| G5 | factor-knowledge | facts the model must simply know: capitals, element symbols and names, unit facts, common science and geography |
| G6 | unseparated relation | paired booking decisions that differ only in one relation: the correct answer flips between ALLOW and HOLD only when the same exclusive seat is contended by a different producer at an overlapping time |

Each grade has three splits — diagnostic, validation, held-out —
disjoint by construction (separate lexical pools and operand sets
per split; prompts and worked derivations are unique across the
whole suite). Sizes: 120 / 60 / 120 items per grade, except G5
(100 / 60 / 100, bounded by the authored fact pool).

## Running it

Requirements: Python 3 with `torch` and `transformers`. A small
model loads on CPU; a GPU makes a full profile take minutes.

Score a model's base performance on every grade and split:

```
python3 run_profile.py --model /path/to/model-dir --out results/base.json
```

The model may be a Hugging Face directory or a single `.gguf`
file. The results JSON contains per-grade, per-split accuracy,
per-category accuracy, and every item's raw output.

Run a patch sequence with retention measurement. The profile runs
in grade order; after each grade's patch, the held-out sets of all
previously profiled grades are re-scored with the patched model,
producing a retention curve over tasks (not a generic forgetting
probe):

```
python3 run_profile.py --model /path/to/base \
    --patch G1=/path/to/patched-g1 --patch G3=/path/to/patched-g3 \
    --out results/sequence.json
```

Grades without a `--patch` entry keep the previous model in the
chain. The output contains a `retention_curve`: one row per stage
with the held-out accuracy of every grade profiled so far.

Regenerate the batteries and verify them (stdlib only):

```
cd batteries
python3 gen_profile.py        # deterministic; same output every run
python3 verify_profile.py     # independent re-check; exit 0 = PASS
```

The verifier re-derives most gold answers from the prompt text
itself (arithmetic, dates via the calendar, the G6 decisions via
the stated policy rule), checks split disjointness and prompt
uniqueness, screens for impossible items, measures cross-split
near-duplication, and emits `audit_sample.jsonl` for label audits.

## Scoring

Decoding is greedy, with the model's chat template applied and
thinking disabled. Every prompt is fixed at generation time; each
item's raw output is saved.

An answer is correct only if the model's whole reply, after
normalisation, equals the gold answer. Normalisation lowercases,
collapses whitespace, removes thousands commas and one trailing
full stop; if both sides parse as numbers they are compared as
numbers. A reply that merely contains the gold string — "The
answer is 42" for gold "42" — scores **wrong**. This is strict by
design: the profile grades failure types, and a model that buries
its answer in prose has a format failure, which is what G1 and G2
exist to measure.

## Reading a profile

A grade's baseline tells you which instrument fits a failure. Low
G1–G3 scores with high G5 indicate behaviour-shaped failures: the
model knows the material and deploys it badly. A collapse at G4
or G5 indicates procedure or knowledge the model does not have.
G6 pairs test a single relation in isolation; because each HOLD
item has a minimally different ALLOW twin, a model cannot pass G6
by class bias — the answer balance is exactly 50/50 in every
split.

## Limitations

- The suite measures the six failure types above, at the scale of
  short mechanically scored tasks. It does not measure open-ended
  generation, reasoning quality in prose, or knowledge beyond the
  authored G5 pool (260 facts).
- G5 facts are authored world knowledge as of writing; a small
  number involve conventions (for example capital-city choices
  for countries with more than one seat of government).
- G6 tests one relation — same-seat contention under one stated
  booking policy — not decision-making in general.
- Greedy decoding is deterministic per configuration, but batch
  composition and hardware numerics can move a borderline item
  between runs; treat accuracies as reproducible to within about
  an item per split.
- The two reference baselines shipped in `results/` were measured
  on Qwen3-0.6B and LFM2-1.2B. They calibrate this instrument;
  they are not rankings of the models in general.
