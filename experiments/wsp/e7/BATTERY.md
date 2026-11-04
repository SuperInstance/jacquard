# E7 battery — the signal-chain soft joint (model / mixed / code)

Built 2026-11-04 by the E7 battery-builder seat for Jacquard Phase 15,
slice E7. The instrument and scorer live here; no model was patched,
run, or consulted in the making of this battery. A coordinator
verifies everything independently — all numbers below are reproducible
from the files in this directory.

## What is being measured

In `signal_chain_dial.py` (read-only clone `~/sigchain-read`), `_score`
is the joint under study. The hard spine extracts features: lexicon
membership counts (`MODEL_WORDS`/`MODEL_PHRASES`, `CODE_WORDS`/
`CODE_PHRASES`, counting each *distinct* word/phrase once) plus a
per-occurrence count of code symbols. The soft joint is the weighting:
every hit counts equally and the balance `(model − code) / total` is
mapped onto [−1, +1]. On mixed messages that equal weighting is where
the reading goes wrong. This battery is the narrow set for coaching
that joint: 3-way classification (code / mixed / model) of single
messages, labels by construction.

## Files

| file | what |
|---|---|
| `gen_joint.py` | deterministic (seeded) generator; writes both splits |
| `diagnostic.jsonl` | 120 items, ids `e7diag-001`…`e7diag-120` |
| `heldout.jsonl` | 120 items, ids `e7held-001`…`e7held-120` |
| `verify_joint.py` | independent structural/leakage checks (13 checks) |
| `score_joint.py` | student scorer for the Thor (see below) |
| `baseline_joint.py` | runs the repo's own `_score` over both splits |
| `baseline_results.json` | full baseline output incl. per-item dial scores |

Item schema: `{"id", "split", "label", "subtype", "boundary",
"message"}`. `boundary: true` marks subtypes designed to sit near the
joint's decision boundary (see below); it is construction metadata,
not a difficulty guarantee (see Weaknesses).

## Construction method

Each item is produced by one of 22 subtype templates. Templates are
hand-written **per split**: the diagnostic pool is a harbour/ferry
operations platform, the held-out pool is a community music school +
garden sensor network + clinic rota tool, and the two pools share no
people, files, functions, topics, everyday contexts, error types, or
sentence frames. Slot-filling (names, files, numbers) is driven by
`random.Random` with fixed per-split seeds (diag 20261104, held
77117711); re-running `gen_joint.py` reproduces both JSONL files
byte-identically (md5-verified across runs).

Process note — a caught failure: the first draft of this generator
shared templates across splits with only slot words differing. The
verifier's cross-split token-Jaccard check caught it (max similarity
0.92 — held-out items were reskins of diagnostic ones). The generator
was rewritten with genuinely disjoint template sets; the same check
now reports max cross-split Jaccard **0.324**. The check stays in
`verify_joint.py` so any regression fails loudly.

### Class definitions (by construction)

- **code** — source code fragments, diffs, stack traces, compiler/log
  output, shell sessions and logs (per the tasking), plus config/data
  files (`config_low_symbol`) — see the stated convention under
  Weaknesses.
- **model** — natural-language prose of the kind the chain processes:
  commit-message prose, status explanations, design notes, chat-style
  technical prose — with **no code fragments** in any model item.
- **mixed** — genuine blends: prose quoting code inline, code with
  long prose comments/docstrings, warm narrative commit messages
  dense with code terms, error-shaped prose (text formatted like a
  stack trace whose content is a human narrative), prose carrying an
  embedded log/shell excerpt, prose followed by a whole code block.

### Balance

Both splits: **120 items = 40 code / 40 mixed / 40 model**, across
22 subtypes (counts per subtype are identical in shape across splits;
templates and content are disjoint). Message length varies widely:
diagnostic 2–50 words (median 32), held-out 3–55 words (median 33).

### Boundary-hard subtypes, and why they are hard for the joint

Flagged `boundary: true` (49 items per split):

- `config_low_symbol` (code) — YAML/TOML/JSON config: almost no code
  symbols and no lexicon hits either way, so the dial has nearly no
  signal and lands near 0 → predicted mixed.
- `prose_identifiers` (code) — real code whose *identifiers* are
  prose lexicon words (`warm`, `gentle`, `memory`, `kind`…). The
  spine counts identifiers as words; the semantics are in the syntax
  it ignores.
- `terse_code` (code) — one-liners with 2–6 tokens of signal; the
  balance is whatever the single lexicon hit says.
- `wordy_query` (code) — SQL/Make spelled out in English words;
  symbol-poor, word-rich.
- `design_note_code_dense` (model) — design prose that must talk
  about `function`, `return`, `error`, `merge`, `commit`, `pipeline`,
  `null`… in full sentences. Every one of those words is a code hit;
  there is not a single code fragment in the text.
- `numbers_units_prose` (model) — measurement prose whose
  parentheses and semicolons are counted as *code symbols* by the
  spine, while the numerals carry no lexicon signal at all.
- `polysemy_prose` (model) — everyday prose where code words appear
  in everyday senses: a school *class* that will *return* after the
  *match*, a *loop* road, a village *function*, radio *static*.
- `terse_prose` (model) — 3–9-word hedged sentences; one lexicon hit
  either way swings the balance to an extreme or leaves it at 0.
- `warm_commit_dense` (mixed) — conventional-prefix commit messages
  (`fix:`/`feat:`/`refactor:`) whose bodies are warm narrative dense
  with code terms; spine features fire on both sides at full strength.
- `error_shaped_prose` (mixed) — stack-trace *shape*, human story
  *content*. The shape contributes `File "…", line …` phrasing and
  invented error names; the content is pure prose. Which side wins
  depends entirely on weighting — the joint itself.

Unflagged subtypes can also be dial-hard in practice (see per-subtype
baseline below — notably `shell_log`, whose plain-word log lines
contain almost no counted features: the token `errors` does not match
the lexicon entry `error`).

## Verification (`verify_joint.py`) — 13/13 PASS

JSONL validity + required fields (both splits); class balance
120 = 40/40/40 (both); id format/uniqueness/sequence (both);
split-field consistency (both); label-field sanity (both); no exact
duplicate messages within or across splits (240/240 unique); no
normalised-text duplicates across splits (overlap 0); no
near-duplicate leakage across splits (max token Jaccard 0.324 <
0.60 threshold).

## Spine+joint baseline (the number the loop must beat)

Method: import `_score` read-only from `~/sigchain-read`, compute the
dial balance per message, map to 3 classes by **equal thirds of the
dial's own range** (balance ≤ −1/3 → code; ≥ +1/3 → model; otherwise
mixed). Equal thirds is the simplest mapping that uses no battery
information; no threshold was tuned on these items. Caveat: the dial
returns exactly 0.0 both for genuinely balanced text and for text
with no signal at all — both land in `mixed` under this mapping.

| split | accuracy | code | mixed | model | boundary items | non-boundary |
|---|---|---|---|---|---|---|
| diagnostic | **61.7%** (74/120) | 28/40 (70.0%) | 19/40 (47.5%) | 27/40 (67.5%) | 42.0% | 75.7% |
| held-out | **46.7%** (56/120) | 25/40 (62.5%) | **3/40 (7.5%)** | 28/40 (70.0%) | 40.0% | 51.4% |

Confusion (gold → predicted):

- diagnostic — code: {code 28, mixed 11, model 1}; mixed: {mixed 19,
  model 18, code 3}; model: {model 27, mixed 7, code 6}.
- held-out — code: {code 25, mixed 11, model 4}; mixed: {model 23,
  code 14, mixed 3}; model: {model 28, code 9, mixed 3}.

Per-subtype dial accuracy (diag / held): plain_function 6/6, 6/6 ·
diff 5/5, 5/5 · stack_trace 5/5, 5/5 · shell_log **0/5, 0/5** ·
config_low_symbol **0/5**, 2/5 · prose_identifiers 3/5, 2/5 ·
terse_code 4/4, 2/4 · wordy_query 5/5, 3/5 · reflective_status 6/6,
6/6 · commit_prose 3/5, 4/5 · design_note_code_dense **0/6, 0/6** ·
chat_prose 5/5, 5/5 · numbers_units_prose 4/5, 2/5 · warm_narrative
5/5, 5/5 · polysemy_prose 1/5, 3/5 · terse_prose 3/3, 3/3 ·
inline_code_quote 6/7, **0/7** · code_long_comments 7/7, **0/7** ·
warm_commit_dense 1/6, 2/6 · error_shaped_prose **0/6**, 1/6 ·
prose_plus_log **0/7, 0/7** · prose_plus_block 5/7, **0/7**.

Reading: the spine handles canonical code and canonical prose. The
joint fails exactly where predicted — mixed items are absorbed by
whichever side's lexicon shouts louder (held-out mixed dial scores
sit at the extremes, e.g. +1.00 for prose quoting a flag rename,
−0.54 for prose introducing a small Go function), and prose that must
use code vocabulary (`design_note_code_dense`, 0/12 across splits) is
read as code. Full per-item dial scores are in
`baseline_results.json`.

## Student scorer (`score_joint.py`) — for later rounds, on the Thor

Not run here (no model on the Oracle; building it was the task,
running it is the loop's). Conventions mirror the phase's `score.py`:
chat template with `enable_thinking=False` (loud failure if the
tokenizer rejects the flag), EOS ids as the union of
`generation_config.json` and the tokenizer, bfloat16, left padding,
greedy decoding, batch 16. E7 specifics: prompt is the fixed
instruction `Classify the message as code, mixed, or model. Answer
with just the label.` + the message; **max 8 new tokens**; predicted
label = first word-boundary occurrence of `code|mixed|model`
(case-insensitive) in the raw output, none → wrong. Output JSON
mirrors `score.py` style (`model` → `splits` → `n` / `accuracy` /
`per_class` / `confusion` / `items[]` with `raw_output`/`correct`),
split name taken from the items' own `split` field.

```
~/ml/.venv/bin/python score_joint.py --model DIR \
    --battery diagnostic.jsonl --out results_e7_diag.json
~/ml/.venv/bin/python score_joint.py --model DIR \
    --battery heldout.jsonl --out results_e7_held.json
~/ml/.venv/bin/python score_joint.py --selftest   # PASS, 10 cases
```

## Known weaknesses (stated plainly)

1. **All items are synthetic and template-generated.** Each subtype
   has only 2–4 templates per split, so within a split, items of a
   subtype share a frame. A student could learn *frames* rather than
   the joint; the disjoint held-out frames are the guard, and they
   only guard across splits, not within diagnostic.
2. **Held-out is harder than diagnostic for the spine** (46.7% vs
   61.7%), mostly because held-out mixed blends sit at more extreme
   prose:code ratios. The splits are balanced in counts, not in
   difficulty; treat them as different instruments, not two draws
   from one distribution.
3. **`boundary` undercounts dial-difficulty in held-out**: several
   unflagged mixed subtypes score 0/7 there. The flag records design
   intent at construction time, not measured difficulty.
4. **Config-as-code is a stated convention, not a task-given one.**
   The tasking lists code as fragments/diffs/traces/compiler-log
   output/shell sessions; `config_low_symbol` (5 items/split) extends
   that to config/data files, the way a repo would. If the loop's
   teacher disagrees systematically on those 10 items, this is why.
5. **Labels are by construction only** — no human or teacher has
   adjudicated a single item. A few blends (e.g. prose_plus_block
   items that are ~80% prose) are mixed *by the task's class
   definitions*; a reader applying a majority-content rule would
   label some of them model. That disagreement is arguably the
   phenomenon under study, but it is a real property of this battery.
6. **Narrow world**: two fictional project domains, one prose voice
   (warm, hedged, first-person — the chain's own register), English
   only, no real commit history or real model output. Generalisation
   beyond this register is untested by construction.
7. The baseline's equal-thirds mapping is a choice. A different
   stated mapping would move the baseline numbers (the per-item dial
   scores in `baseline_results.json` let anyone recompute under
   another mapping without re-running anything).
