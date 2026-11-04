# Slice 45 (Phase 16, R2) — patchability profile instrument: build record

Builder: battery-builder worker (slice 45). Scope: build and
verify the graded battery suite and harness, run base baselines
for both students. Patching and final grading are other roles;
this record is the builder's evidence for the independent
reviewer required by CRITERIA.md R2 ("Battery acceptance").

## What was built

`experiments/wsp2/profile/`:

- `batteries/gen_profile.py` — deterministic generator (stdlib
  `random`, fixed seeds per grade). Regeneration is byte-identical.
- `batteries/*.jsonl` — 18 split files, 1,740 items total:
  G1–G4 and G6 at 120 diagnostic / 60 validation / 120 held-out;
  G5 at 100 / 60 / 100 (bounded by the authored fact pool: 260 of
  270 authored facts are used, each in exactly one split; 10
  authored facts are unused — corrected per review R2-F3).
- `batteries/verify_profile.py` — independent verifier (imports
  nothing from the generator); output saved in
  `batteries/VERIFY-PROFILE.txt`; deterministic label-audit sample
  in `batteries/audit_sample.jsonl` (116 items).
- `batteries/manifest.json` — per-split counts and category mix.
- `run_profile.py` — harness with `base` mode (all grades ×
  splits), `sequence` mode (grade-order profiling with patched
  model directories; after each grade, held-out of every
  previously profiled grade is re-scored — the task-held-out
  retention curve), and `--selftest` for the matcher.
- `README.md` — production-voice tool documentation.
- `results/qwen3-0.6b-base.json`, `results/lfm2-1.2b-base.json` —
  base baselines (instrument calibration), per-item outputs saved.

Grade design: G1 format/completion (copy, trivial sums, sequence
continuation, yes/no compare, last word); G2 framing (negated
odd-one-out, false claims, distractor facts, quoted questions,
order-swapped comparisons — G1-level content); G3 readout
(vowel/consonant start, letter containment, case, plurality, word
length, unambiguous sentiment); G4 procedure (2026 date arithmetic
in the Phase 15 T2 lineage — days-between, weekday offset,
add-days-to-month, whole months with the birthday rule — plus
week decomposition and two-step arithmetic chains; three disjoint
frame sets, one per split, including a numeric DD/MM/YYYY frame
for held-out); G5 factor-knowledge (authored tables, 270 facts in total:
88 capitals, 64 element facts (40 name->symbol + 24
symbol->name), 28 solar, 30 unit facts, 36 animal/misc, 24
history/misc — shuffled with a fixed seed and partitioned
contiguously; the first 260 are used (100 diagnostic / 60
validation / 100 held-out) and the remaining 10 are unused);
G6 unseparated relation (paired booking contexts in the E8
geometry: 60/30/60 minimal pairs per split; the pair's two items
differ in one relation component — seat, box, time, lane, or
expiry — and their golds flip ALLOW/HOLD. Field-level purity,
corrected per review R2-F2: different_seat, different_box and
same_lane_renewal twins differ in exactly 1 field; time_disjoint
twins differ in 2 fields (the new start and its derived
check-by — one underlying component); expired_booking twins
rewrite 2–4 fields of the EXISTING booking (its check-by, the
expiry note, and often its start and/or duration), so the
expiry twin is not the same booking with one component
flipped. All golds were independently recomputed correct by
the reviewer regardless. Every split is
exactly 50% ALLOW / 50% HOLD, so a constant classifier scores
exactly 50 and class bias cannot pass).

Matcher: exact normalised-answer matching (documented in
run_profile.py and README.md). A reply that merely contains the
gold string scores wrong — the Phase 15 fact-matcher defect class
(crediting incidental containment) is excluded by construction
and pinned in the harness selftest (19 cases, all PASS).

## Verification results

Verifier: **PASS** (exit 0).

- 1,461 golds recomputed from the prompt text alone with fresh
  parsing logic (all of G1/G2 except odd-one-out membership, G3
  surface rules, all of G4 via `datetime`, all of G6 via the
  stated policy rule); 0 unparseable; 0 mismatches. G4
  derivations additionally recomputed with a restricted AST
  evaluator; G4 prompts' stated weekdays checked against the real
  2026 calendar.
- Prompt uniqueness: 1,740 / 1,740 unique across the whole suite.
- Impossible-item screen: answer-set membership per category,
  G6 interval sanity and pair integrity (every pair_id has
  exactly 2 items with golds {ALLOW, HOLD}) — all pass.
- G5 fact disjointness: 260 distinct fact keys, none in two
  splits (checked by the verifier).
- Cross-split near-duplicate screen (token-set Jaccard, held-out
  vs diagnostic+validation, max per grade): G1 0.889, G2 0.800,
  G3 0.857, G4 0.528, G5 0.875, G6 0.902. The high values are
  frame-token overlap on short templated prompts (inspected: the
  worst pairs differ in content and usually in gold); the leakage
  controls are the disjoint pools and unique prompts/derivations,
  both verified. See defect D2 for the one real weakness this
  screen found and its fix.
- Builder's manual label audit: all 116 audit-sample items read;
  labels correct. Two text defects found and fixed (D3).

## Base baselines (strict matcher; accuracy %)

Qwen3-0.6B (base, ~/wsp-exp/models/Qwen3-0.6B):

| grade | diagnostic | validation | held-out |
|---|---|---|---|
| G1 | 18.3 | 18.3 | 17.5 |
| G2 | 3.3 | 5.0 | 3.3 |
| G3 | 40.8 | 25.0 | 40.8 |
| G4 | 0.0 | 0.0 | 0.0 |
| G5 | 16.0 | 13.3 | 18.0 |
| G6 | 50.0 | 50.0 | 50.0 |

LFM2-1.2B (base, GGUF Q8_0 dequantised by transformers):

| grade | diagnostic | validation | held-out |
|---|---|---|---|
| G1 | 59.2 | 56.7 | 51.7 |
| G2 | 33.3 | 36.7 | 30.0 |
| G3 | 32.5 | 28.3 | 31.7 |
| G4 | 9.2 | 8.3 | 12.5 |
| G5 | 80.0 | 73.3 | 81.0 |
| G6 | 0.0 | 0.0 | 0.0 |

The two students' profiles are near-mirror images, which is the
calibration signal that the grades separate failure types rather
than ranking models: LFM2 carries the facts (G5 73–81) and
deploys them passably (G1 52–59) but reads surface properties
poorly (G3 ~30, with genuine readout errors, e.g. 'pillow'
reported to contain 'e'); Qwen3-0.6B reads comparatively better
and knows far less. On G6 the two are degenerate in opposite
directions: Qwen answers ALLOW on 300/300 items across splits;
LFM2's every G6 output begins with HOLD on 300/300 items but
continues with reasoning prose, so under the strict matcher it
scores 0.0 while Qwen's bare ALLOWs score exactly 50.0. A
first-token readout would put both at 50.0 — neither model has
any G6 decision surface at base.

Calibration notes (builder's reading of the per-item outputs,
not scores): Qwen3-0.6B answers ALLOW on 120/120 G6 held-out
items — a constant classifier, reproducing the Phase 15 E8 base
finding; the balanced G6 design reports that as exactly 50.0.
On G1 held-out, the gold string appears somewhere in the output
for 82/120 items while only 21/120 replies are exactly the gold:
the gap is format failure mass, which is what G1 exists to
measure. On G4 held-out, even Phase 15's lenient last-number
extraction would credit only 12/120 — the G4 zero is procedure
mass, not only format (e.g. a 21-day gap answered as 10 days).

## Defects found

- D1 (harness, mine, fixed): the first harness version batched
  with right padding and sliced continuations at the padded
  width, producing empty outputs for shorter prompts and a
  first Qwen run with meaningless scores (G1 12.5, G5 0.0).
  Caught by inspecting raw outputs against Phase 15's known base
  behaviour; fixed with left padding; the discarded run's JSON
  was overwritten by the corrected run and is not in the tree.
- D2 (battery, mine, fixed): the Jaccard screen found true
  content near-duplicates across splits — commutative operand
  swaps ("15 + 18" diagnostic vs "18 + 15" held-out; reversed
  comparisons with flipped golds). Fixed with canonical content
  keys (sorted operand pairs) deduplicated across all splits;
  max G1 Jaccard fell from 1.000 to 0.889 (frame tokens only).
- D3 (battery text, mine, fixed): audit sample caught "NOT a
  animal / a instrument" article errors in G2 (13 items) and
  one convoluted G5 question; both fixed and regenerated.
  The same paragraph originally also claimed a "caterpillars"
  misspelling had been caught and fixed. That claim was false
  in both directions, and the reviewer repeated it (R2-F3):
  the builder's audit misread the word, the "fix" applied was
  a no-op string replacement, and the check that appeared to
  confirm it searched for the very string it believed was the
  typo. Byte-level adjudication in the fix round: every
  occurrence of the word in the tree (generator, g5-diag-035,
  audit sample) is byte-identical to the "caterpillars" entry
  in /usr/share/dict/words on the Thor (bytes
  99 97 116 101 114 112 105 108 108 97 114 115; aspell
  accepts it and rejects the single-l variant). The word was
  never misspelled, and no change was made to it in the fix
  round — changing it would have introduced a misspelling
  and altered battery content. The lesson stands with D1:
  a verification that cannot fail is not a verification.
- D4 (generator, mine, fixed during build): G6 pair ids restarted
  per split, colliding derivations across splits (validation
  generation initially exhausted at 43/60); G3 word pools were
  consumed by popping and exhausted at 26/120; a G5 derivation
  truncated at 40 chars collided two colour-mixing facts
  (validation landed at 59/60). All fixed; final verifier PASS
  is on the regenerated suite.
- D5 (inherited, reported, not fixed — not mine to change):
  Phase 15's `score.py` arithmetic rule extracts the LAST number,
  so any trailing incidental number wins; documented there as
  deliberate. The profile harness does not inherit the rule.
- D6 (environment, noted): the Thor's LFM2-1.2B exists only as a
  Q8_0 GGUF. It loads in transformers only via the `gguf_file`
  route (the naive path — passing the .gguf to from_pretrained —
  fails with a config OSError), dequantising to float weights;
  `causal_conv1d` is not installed, so its convolution layers run
  a reference PyTorch fallback (correct, slower). Baselines were
  measured through that route; no substitute model was used.
- D7 (design limit, stated): G2's odd-one-out and distractor
  categories are pool-bounded (5/3/5 items per split); the grade
  total is carried by the other three categories. G3's sentiment
  and plural categories are likewise small (5/3/5 and 5/3/5).
  Counts are in manifest.json; a reviewer weighing category-level
  conclusions should use the per-category numbers in the results
  JSON, not the grade totals.

Harness verification: matcher selftest PASS (19 cases at
build; 26 after the R2-F1 fix). Sequence mode smoke-tested on
the Thor with the base model standing in as its own G1 patch:
the emitted retention curve has the base row plus one row per
grade in profile order, each re-scoring only the grades
profiled so far, and every value reproduces the base-mode
held-out accuracies exactly (a reproducibility check on the
whole pipeline: two independent runs, identical accuracies on
all 18 grade/split cells for Qwen3-0.6B). The full-scale
smoke artefacts for both students are committed as
results/qwen3-0.6b-sequence-smoke.json and
results/lfm2-1.2b-sequence-smoke.json (see Review fixes,
R2-F4).

## Review fixes (independent review: PASS-WITH-FIXES)

The reviewer's record is on branch p16-r2-review
(profile/REVIEW.md). Fixes applied on p16-r2:

- R2-F1 (matcher accent-folding): normalise_answer now folds
  accents on both sides (NFKD, combining marks removed);
  selftest pins the behaviour in both directions (26 cases,
  PASS). G5 was re-run for BOTH models on all splits with the
  fixed matcher and the new G5 sections were spliced into the
  committed baseline JSONs (all other grades' records are the
  originally audited ones, byte-preserved). Old -> new G5
  accuracies: Qwen3-0.6B 16.0 / 13.3 / 18.0 -> unchanged in
  every split (its re-run also reproduced all 18 grade/split
  cells of the original run exactly). LFM2-1.2B: diagnostic
  77.0 -> 80.0, validation 70.0 -> 73.3, held-out 81.0 ->
  81.0. The five flipped items are exactly the reviewer's
  accent cases, with identical raw outputs: Malé, Bogotá,
  Asunción (diagnostic), Brasília, Reykjavík (validation).
  (Side effect, harmless here: NFKD also folds compatibility
  characters in the stored normalised_output fields — e.g.
  subscript digits in chemical outputs, "N\u2082" -> "n2" —
  visible in the Qwen G5 diff; no correct flag changed
  anywhere except the five accent items above.)
  The remaining discredit class the reviewer named —
  leading-article and plural replies ("The Sun", "The
  telephone.", "Kittens") — was deliberately NOT fixed: the
  whole-reply discipline is the instrument's design, and the
  review itself calls that the stricter call.
- R2-F2 (G6 pair purity): the claim is corrected in the G6
  design paragraph above, with the reviewer's field-level
  counts. No battery content changed.
- R2-F3 (fact-pool counts + D3): counts corrected above and
  in D3 (270 authored, 88 capitals, 64 element facts, 260
  used, 10 unused). The spelling sub-claim is adjudicated
  in D3: the word is byte-identical to the dictionary
  spelling; no change was made, and no gold, split
  membership, or battery content changed anywhere in this
  fix round (batteries are byte-identical to the audited
  commit; verify_profile.py still PASSes).
- R2-F4 (sequence artefact): full-scale sequence smokes run
  for both students (base model as its own G1 patch) and
  committed: results/qwen3-0.6b-sequence-smoke.json and
  results/lfm2-1.2b-sequence-smoke.json. In both, the final
  retention row equals the base-mode held-out accuracies on
  every grade. (Process note: the first fix-round launch of
  these runs silently no-oped — a heredoc expansion bug in
  the builder's driver script emptied the interpreter path,
  and its DONE markers were unconditional. Caught by the
  missing output files, re-run with per-run failure markers;
  the artefacts above are from the real runs.)
- R2-F5 (G6 offset limit): stated in the README limitations —
  G6's start offsets are bimodal with no near-boundary items,
  so the grade cannot distinguish representing overlap from
  reading start offset conjunctively with seat/box/producer
  equality.

## Retention design note

Retention is task-held-out throughout, per the Phase 15
methodological finding (SLICE43-FINDINGS.md): `sequence` mode
re-scores previously profiled grades' HELD-OUT splits after each
grade's patch. No generic forgetting battery is part of this
instrument.
