# Slice 45 (Phase 16, R2) — INDEPENDENT REVIEW of the patchability-profile battery suite and harness

Reviewer: independent reviewer (slice 45 R2 audit role; did not build
the suite, authored no patches, edited no battery). Audited branch
`p16-r2` @ 9139178. Audit run 2026-11-03 (AKST) on the Oracle (static
audits, regeneration) and the Thor (live re-scoring, copies only —
no resident or Phase 15/16 artefact was mutated). All recomputation
code was written fresh for this review; neither `gen_profile.py` nor
`verify_profile.py` was imported or reused.

## VERDICT: PASS-WITH-FIXES (no blocking defects)

No wrong gold, no gold-determining split leakage, no matcher
mis-crediting, and no reproducibility failure was found. Patching
under CRITERIA.md R2 may proceed. Five non-blocking defects/limits
are named below (R2-F1..R2-F5); R2-F1 and R2-F4 should be fixed or
explicitly carried before G5 yield readings and the sequence smoke
claim are relied on at face value.

## 1. Gold correctness (independent recomputation)

Method: stratified random sample (reviewer seed 20261103), 24 items
per grade×split cell for G1–G5, 10 per cell for G6, plus forced
inclusion of ALL G2 `not_category` (13), ALL G3 `plural_check` (13)
and `sentiment` (13) items, plus ALL 120 G6 held-out items: **529
unique items attempted, 457 golds recomputed from prompt text alone,
0 mismatches, 0 unparseable.** The 72 sampled G5 items were judged
as facts (see below), not recomputed.

Extended beyond the sample, same fresh code:

- **G4 full battery: 300/300 recomputed with real calendar
  arithmetic (`datetime`), 0 mismatches, 0 flags.** Every weekday
  stated in a `weekday_offset` prompt was checked against the real
  2026 calendar: all true. All three date frames (incl. the held-out
  DD/MM/YYYY frame) parse and agree.
- **G6 full battery: 300/300 recomputed** by parsing both booking
  blocks and applying the policy stated in the prompt text, 0
  mismatches.
- G1/G2/G3 sampled categories (copy, adds, sequences incl. ABAB,
  comparisons, claims, quoted questions, distractors, odd-one-out
  against a reviewer-authored membership lexicon, vowel/contains/
  case/length/plural/sentiment against reviewer-authored references):
  0 mismatches. Two apparent G4 mismatches during the audit were the
  reviewer's own parser misreading the validation remainder frame;
  the stored golds were correct on hand-check (e.g. 100 days →
  remainder 2). Recorded here because the audit's false alarms are
  part of its evidence.

**G5 facts — all 260 items judged** (not just the 72 sampled)
against the reviewer's own knowledge: 88 capitals, 64 element facts
(40 symbol + 24 name), 28 solar, 30 unit, 36 animal/misc, 24
history/misc. **No hard-wrong fact found.** Convention-suspects,
all standard school-level readings, none counted as errors:
Bolivia → Sucre (constitutional capital; seat of government is
La Paz), Sri Lanka → Colombo (legislative capital is Sri
Jayawardenepura Kotte), Netherlands → Amsterdam, Switzerland →
Bern, Venus "day longer than its year" (true of the sidereal
rotation; the solar day is shorter), Nile as longest river, Edison
as light-bulb inventor, Earth orbit "365 days", 7 continents. The
README already discloses the capital-convention class.

## 2. Split hygiene beyond Jaccard (semantic leakage hunt)

Canonical-content screens (operands/subjects extracted from prompt
text, frames and names stripped):

- **G4: 0 exact operand-tuple overlaps across splits in every
  category** (date pairs, date+offset, week counts, chain operands —
  20–22 distinct held-out keys per category vs 26–32 earlier keys).
  The algebraically-identical-under-a-different-frame leak the
  builder's derivation-dedup was meant to block is indeed absent.
  Residual: ~11 single calendar dates recur across splits in
  *different* categories with *different* offsets (e.g. 2026-08-24
  in a diagnostic and a held-out `add_days_month` with different
  n, coincidentally the same gold month). No gold-determining
  content is shared.
- **G1/G2: 0 exact canonical-key overlaps across splits** in every
  category (add pairs, comparison pairs+gold, sequence start+step,
  copy words — the per-split word pools verified disjoint by
  inspection — distractor tuples, odd-one-out answers). Pooled
  across G1+G2 categories, 7 of 441 operand pairs recur in another
  split under a *different* task (e.g. (6,18) as a diagnostic
  `small_add` and a held-out `order_swap`): different gold form,
  negligible.
- **G5: 0 same-fact re-asks across splits.** The verifier's
  entity-key screen (260 distinct keys) was confirmed in substance:
  capitals are partitioned by country, the two element tables use
  disjoint element sets, and no question is re-worded into another
  split. Planet subjects recur (Venus is the answer in all three
  splits, to *different* facts: second-from-Sun / Morning Star /
  hottest / day-vs-year) — subject familiarity, not fact leakage;
  no item's gold is determined by another split's item.
- **G6: 0 of 120 held-out scenario skeletons** (box, seat, existing
  start, duration, new-start offset, category — lanes/tasks
  stripped) appear in diagnostic+validation. Lanes and tasks are
  disjoint per split by construction and verified in the items.

Builder's Jaccard maxima (G1 0.889 … G6 0.902) are frame-token
overlap on short templated prompts, as the builder stated; the
canonical screens above are the stronger evidence and they are
clean.

## 3. G6 integrity

- Balance: recounted — exactly 50% ALLOW / 50% HOLD in every split
  (60/60, 30/30, 60/60); all 150 pair_ids have exactly 2 items with
  golds {ALLOW, HOLD}.
- Policy coherence: the generator's rule (HOLD iff same box+seat,
  different producer, overlapping planned windows, existing booking
  not past check-by) matches the SLICE43-E8 notion of
  same-exclusive-seat contention, and the prompt states the policy
  facts to the model, so items are self-contained. My independent
  policy recomputation agrees on 300/300 items.
- Minimal pairs — **partially as claimed (see R2-F2):** field-level
  diff of each pair's two prompts: `different_seat` 41 pairs,
  `different_box` 23, `same_lane_renewal` 28 differ in exactly 1
  field; `time_disjoint` 31 pairs differ in 2 fields (new start +
  its derived check-by — one underlying component);
  `expired_booking` 27 pairs differ in 2–4 fields, all on the
  *existing* booking (check-by, note, and in 20 of 27 its start
  and/or duration are also rewritten). The expiry twin is therefore
  not the same booking with one component flipped.
- Surface cues: prompt length vs gold, Mann-Whitney U per split —
  diagnostic p=0.264, validation p=0.391, held-out p=0.075; with
  expired ALLOW items excluded (they carry the legitimate
  "(check-by passed, no heartbeat)" cue) p=0.875 / 0.399 / 0.897,
  means within 3 characters. New-request seat × gold and box × gold
  distributions are balanced in all splits. No spurious cue found.
- Storage order: all 150 pairs are stored HOLD-first / ALLOW-second
  and twins are adjacent in file order. Inert under this harness
  (items are scored independently), noted for any future
  sequential-context use.

## 4. Matcher edges (committed baseline JSONs)

- My independently re-implemented matcher (from the README spec)
  was applied to **all 3,520 per-item records** in both baseline
  JSONs: **0 correct-flag disagreements**, and every committed
  accuracy recomputes exactly from the flags and from my recheck.
- False credits: none found. There are 0 correct-but-string-
  different (numeric-form) credits in either baseline; every credit
  is an exact normalised match.
- False discredits: heuristic sweep (accent-folded equality,
  spelling variants, leading "the", spacing, trailing-s) over all
  incorrect records found **8 human-plausible discredits, all in
  LFM2 G5** (8/1,760 LFM2 records; 0 in Qwen): Malé, Bogotá,
  Asunción, Brasília, Reykjavík answered with correct accents
  against ASCII golds (Male, Bogota, Asuncion, Brasilia,
  Reykjavik), plus "The Sun", "The telephone.", "Kittens". Two of
  the 8 sit in G5 held-out = 2 points, against the R2 yield bar of
  +3 — see R2-F1. The remaining discredits sampled (24 random
  incorrect outputs eyeballed across grades) are genuine format
  failures by the documented design (prose-wrapped answers, e.g.
  LFM2's G6 HOLD-plus-reasoning outputs; gold-as-token containment
  in 872 incorrect records is discredited deliberately and is the
  Phase 15 defect class the matcher exists to exclude).
- Harness selftest: **PASS** (19/19), run by the reviewer on the
  Oracle and again on the Thor.
- Builder's calibration claims spot-verified against the JSONs:
  Qwen G6 output is exactly "ALLOW" on 300/300; LFM2 G6 output
  begins with "HOLD" on 300/300; Qwen G1 held-out exact-correct 21
  with the gold string appearing (case-insensitively) in 82/120
  outputs; Qwen G4 held-out under a lenient last-number rule would
  credit 12/120. All as stated in SLICE45-BUILD.md.

## 5. Instrument reproducibility (Thor, copies in /tmp only)

- **G3 on Qwen3-0.6B re-run in full** (300 items, harness copy with
  the grade list narrowed to G3): accuracies reproduce exactly
  (40.83 / 25.0 / 40.83) and **300/300 raw outputs are byte-identical
  to the committed JSON, 300/300 correct flags identical.**
- **LFM2-1.2B G6 diagnostic, first 24 items**, via the documented
  GGUF route (`--model …/LFM2-1.2B-Q8_0.gguf`, the harness's
  `gguf_file` branch — README's ".gguf file" claim is accurate, as
  is SLICE45 D6's account of the loading path): G6 accuracy 0.0
  reproduced; 21/24 raw outputs identical, the 3 differences are
  prose-only after an identical first token (HOLD in 24/24 in both
  runs) and 24/24 flags identical — consistent with the README's
  batch-composition numerics caveat.
- Regeneration (Oracle, in a copy): `gen_profile.py` reproduces
  **all 18 battery files and manifest.json byte-identically**;
  `verify_profile.py` exits 0 and its output matches the committed
  VERIFY-PROFILE.txt. README's entry points and scoring description
  match the harness's behaviour as run.

## 6. Retention design (sequence mode)

Code inspection plus a live trimmed replication (Thor; batteries
trimmed to the first 12 items per file in a copy; Qwen3-0.6B with
the base model patched in as its own G1 and G4 patch):

- Retention rows re-score **held-out splits only**, of the grades
  profiled so far (row keys grow G1 → G1..G6 in profile order). No
  diagnostic/validation data enters a retention row, and no generic
  forgetting probe exists anywhere in the harness — retention is
  task-held-out throughout, as CRITERIA R2 requires. (Each stage
  additionally scores its *own* grade on all splits; that is the
  profiling measurement, not retention.)
- Base-mode equivalence in my replication: the sequence base row
  and every after-grade row reproduce the base-mode held-out
  accuracies exactly (trimmed sets: G1 25.0, G2 25.0, G3 75.0,
  G4 0.0, G5 16.67, G6 50.0 at every stage, same model in chain).
- **However**, the full-scale smoke test SLICE45-BUILD.md cites
  ("reproduces … all 18 grade/split cells") has **no committed
  artefact** in the tree — see R2-F4. My replication supports the
  mechanism at trimmed scale; the claim as written is not
  evidenced by the tree.

## Non-blocking defects (builder's fixes, separate step)

- **R2-F1 — matcher/G5 orthography.** G5 golds are ASCII-folded
  while correctly accented answers are discredited (8 instances in
  the LFM2 baseline, 2 in G5 held-out). The matcher is applied
  identically to base and patched runs, so deltas are largely
  safe, but with a +3-point yield bar a ~2-point orthography term
  in G5 held-out should not be left in the instrument. Fix:
  accent-fold both sides in `normalise_answer`, or author the
  accented golds. Also "The Sun"/"The telephone."-type article
  discredits (2 instances) — same fix conversation, stricter call.
- **R2-F2 — G6 minimal-pair claim overstated.** `expired_booking`
  twins (27/150 pairs) rewrite up to 4 fields of the existing
  booking; they are not "exactly one relation component" diffs as
  SLICE45-BUILD.md states. Golds are all correct and no cue leaks
  from it (§3), so this is a claim/purity fix: regenerate expired
  twins holding the existing booking fixed and moving only its
  check-by (+ note) — coherent, since check-by is a heartbeat
  deadline, not the booking's end — or amend the claim.
- **R2-F3 — SLICE45-BUILD.md fact-pool counts are wrong.** The
  authored pool is **270 facts (88 capitals, 64 element facts)**,
  not "260 distinct facts (90 capitals, 65 element facts)"; the
  contiguous 100/60/100 partition leaves **10 authored facts
  unused** (incl. Canada → Ottawa, Cs → caesium, Mercury-closest,
  Moon-satellite). No battery item is affected; the sentence
  "each fact assigned to exactly one split" should read "260 of
  270 authored facts used, each in at most one split". Separately,
  defect D3's claim that the "caterpillars" misspelling was fixed
  is false: it persists in `gen_profile.py` (ANIMAL_MISC) and in
  item g5-diag-035. Gold ("butterflies") unaffected.
- **R2-F4 — sequence smoke artefact not committed.** See §6.
  Commit the full-scale smoke JSON, or soften the SLICE45 claim
  to the trimmed replication this review performed.
- **R2-F5 — G6 design limit (wording, not labels).** New-start
  offsets are bimodal: contention +15/+30/+45 min, time-disjoint
  +90/+120/+150 min, with no near-boundary items (start exactly at
  the existing end; overlap by a few minutes; offset < duration
  but non-overlapping). G6 therefore cannot distinguish a model
  that represents overlap from one that reads start-offset
  conjunctively with seat/box/producer equality. Acceptable for a
  profile grade, but R2's boundary-map language should not claim
  more than this design measures.

## What was NOT found

No wrong gold in 457 sampled recomputations + 600 full-battery
recomputations (G4, G6) + 260 judged facts; no impossible items;
no cross-split item whose gold is determined by another split's
item; no matcher false credit in 3,520 records; no accuracy in
either baseline that fails to recompute; no reproducibility drift
beyond the documented batch-numerics prose wobble (flags stable).

— Reviewer, slice 45 R2 audit. Audit scripts (fresh code) were run
from /tmp on both boxes and are not committed; every number above
is reproducible from the committed batteries and results JSONs
with the methods stated.
