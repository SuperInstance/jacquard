# Phase 16, slice 44 — R1: the E8 transfer autopsy

Worker role: battery + scoring (R1). No patch was authored,
built, or applied in this slice; the only models scored are
the unpatched base student and the PRESERVED Phase 15 round-1
patched student, exactly as found on the Thor.

Question (pre-stated in experiments/wsp2/CRITERIA.md, R1,
hash-bound into the governance log before any test ran):
was E8 round 1's zero held-out transfer caused by (a) FORMAT
ERAS — held-out items arriving in surface formats the
diagnostic era never showed — or (b) the student's
representations not carrying the operator's weighting?

**Verdict, up front: TRANSFER DOES NOT APPEAR under
canonicalisation. The door closes as a REPRESENTATION claim,
with the failing relations named in section 5. No governed
patch round follows from R1 — per CRITERIA.md, that round was
conditional on transfer appearing.**

Artefacts and bench (all work on copies; nothing under
~/wsp-exp/e8/ or ~/wsp-exp/models/ was written):

- Bench: Thor, ~/wsp-exp16/r1/ (batteries/, scripts/,
  results/). Python ~/ml/.venv, torch 2.11.0, CUDA.
- Base student: ~/wsp-exp/e8/work/student-base — verified
  byte-identical weights to the pristine base
  ~/wsp-exp/models/Qwen3-0.6B (model.safetensors md5
  fed58aa6b81fb7e1e6a825af34b3f2dd for both).
- Patched student: ~/wsp-exp/e8/round1/patched-r1 — its
  edits.json and patch.py are md5-identical to the repo's
  patch definition (experiments/wsp/patches/e8-r1/:
  edits.json md5 1b76c78a583fcccf77dffd47f0625640,
  patch.py md5 bd87bce23fab51151aa58813902e8196; the copies
  inside patched-r1/, in round1/, and in the repo all agree).
- Batteries: the Thor copies under ~/wsp-exp/e8/batteries/
  are md5-identical to the repo's experiments/wsp/e8/
  (diagnostic.jsonl 57c049c8e14d2e0db3f80a050f0d4fcc,
  heldout.jsonl 1ae89a1341d048064563526d8c94793b).
- Scorer: Phase 15's score_decision.py, unmodified
  (md5 596b8b831941c65a4ce59f6dca9aa254, Thor copy == repo
  copy); its built-in selftest passes (14 cases).

## 1. Sanity: Phase 15 numbers reproduce exactly

Scored with the Phase 15 path (greedy, chat template with
enable_thinking=False, 8 new tokens, batch 16) on the
ORIGINAL batteries. Results files:
results/sanity_{base,patched}_{diagnostic,heldout}.json

| model | set | (a) operator | (b) correctness | answers |
|---|---|---|---|---|
| base | diagnostic n=112 | 64.29% (72/112) | 59.05% (62/105) | ALLOW 112 |
| base | held-out n=53 | 88.68% (47/53) | 64.29% (9/14) | ALLOW 53 |
| patched r1 | diagnostic n=112 | 96.43% (108/112) | 93.33% (98/105) | ALLOW 75 / HOLD 35 / DENY 2 |
| patched r1 | held-out n=53 | 88.68% (47/53) | 64.29% (9/14) | ALLOW 53 |

Against the Phase 15 record (SLICE43-E8.md): diagnostic
64.3 -> 96.4 on (a), 59.0 -> 93.3 on (b); held-out
(a) 88.7 / (b) 64.3 — every figure reproduces (59.05 rounds
to the record's 59.0). On held-out, patched and base are
ITEM-IDENTICAL (53/53, extracted answer and raw output).
On the three diagnostic incumbent-wrong items (the crux
trio: e8-board-shadow-018, -025, -033; recorded ALLOW,
correct HOLD) the patched student answers ALLOW, ALLOW,
ALLOW — as Phase 15 found. The instrument is not broken;
the autopsy proceeds.

## 2. The format eras, characterised concretely

Both eras were rendered by ONE curation program
(experiments/wsp/e8/curate.py), from three renderer
families. The era difference is real but narrower than the
Phase 15 record's phrasing ("formats the curriculum never
showed") suggests — see defect note D1.

Renderer families (labelled segments, '; '-separated,
policy facts last):

- BOARD (board_items()): producer; effect; resource;
  start; planned duration; check-by; task; contention;
  policy facts. Used for board-shadow items in BOTH eras —
  the identical function and template; a held-out board
  item is already in the diagnostic board format.
- KERNEL (kernel_items()): producer; class; effects;
  requests; standing rule in force for this shape;
  [enrich segments]; policy facts. The diagnostic era's
  kernel items (proof-run, proof-run-2) carry NO enrich
  segments. The held-out era's gpu-windows items INSERT
  enrich segments — "command shape:", "job name:",
  "uses:" — between the standing-rule segment and policy
  facts; that insertion is the only renderer-level novelty
  in either era. slice30-booking items use the plain
  6-segment kernel form.
- PROSE (jev_items()): free prose paragraphs, no labels.
  Diagnostic era only; no prose item exists in held-out.

Era mix (the larger difference is which families appear):

| source | era | n | share | gold | avg ctx chars |
|---|---|---|---|---|---|
| board-shadow | diagnostic | 56 | 50.0% | ALLOW 56 | 477 |
| proof-run-2 | diagnostic | 36 | 32.1% | HOLD 27 / ALLOW 9 | 352 |
| jev (prose) | diagnostic | 11 | 9.8% | ALLOW 6 / DENY 3 / HOLD 2 | 207 |
| proof-run | diagnostic | 9 | 8.0% | HOLD 8 / ALLOW 1 | 344 |
| board-shadow | held-out | 25 | 47.2% | ALLOW 25 | 488 |
| gpu-windows | held-out | 16 | 30.2% | ALLOW 10 / DENY 5 / HOLD 1 | 361 |
| slice30-booking | held-out | 12 | 22.6% | ALLOW 12 | 392 |

Content-level (not rendering) differences inside the shared
kernel family: held-out class vocabulary is new
(gpu-bench, config — diagnostic kernel classes are
agent-read / agent-shell / agent-write shapes), producers
are new (jacquard-build, operator, mystery-lane), and the
policy-facts TEXTS are new (gpu-bridge-policy/1… for
gpu-windows; an extended policy/1 text for slice30-booking;
the board policy text is identical across eras). Those are
facts of the record, not formats, and canonicalisation
preserves them verbatim. Label surface of the answer is
unchanged across eras (the scorer's prompt and the
ALLOW/HOLD/DENY extraction are era-independent).

So, precisely: of the 53 held-out items, 37 (25 board +
12 slice30) already arrive in a format the diagnostic era
used verbatim; 16 (gpu-windows) arrive in the diagnostic
kernel format plus one renderer novelty (enrich insertion);
and ALL of held-out's non-ALLOW golds (5 DENY + 1 HOLD)
sit in those 16 gpu-windows items. The diagnostic era, in
turn, never shows a prose item to held-out: its 11 jev
prose items have no held-out counterpart.

## 3. Canonicalisation and its verifier

Builder: canonicalise.py (this directory). Verifier:
verify_canonical.py — an independent implementation (a
separate regex-based segmenter that re-derives every
expected rendering from the ORIGINAL batteries only and
compares byte-for-byte; it shares no transform code with
the builder).

(i) heldout_canonical.jsonl (n=53) — held-out re-expressed
in the diagnostic era's canonical format:
- board-shadow (25): identity — already diagnostic board
  format (section 2).
- slice30-booking (12): identity — already the exact
  diagnostic kernel 6-segment form; policy text preserved
  verbatim (content, not rendering).
- gpu-windows (16): enrich segments removed as standalone
  segments and folded, in original order, labels and values
  verbatim, onto the tail of the requests segment —
  yielding the exact diagnostic kernel form. (Diagnostic
  requests segments are where job-identifying detail lives:
  shell commands, write targets, booking specs.)

(ii) diagnostic_crossformat.jsonl (n=112) — diagnostic
re-expressed in a held-out-era format (target: the kernel
form, the only decision-log format the held-out era uses;
the held-out era itself renders bookings in kernel form —
the slice30-booking source is board bookings rendered so):
- proof-run / proof-run-2 (45): identity — already kernel
  form; they carry no enrich content.
- board-shadow (56): rendered in kernel form — producer
  verbatim; class "booking" (the class curate.py's board
  sequencer submits for every board row); effects "write";
  requests = the render_requests() booking rendering
  ("write booking/<box>/<seat> start <start>; planned:
  <duration>; check-by: <check-by>") with the board task
  and contention facts appended verbatim; standing rule
  "none recorded" (the board record carries no
  standing-rule fact; the placeholder is curate.py's own
  convention); policy facts verbatim.
- jev (11): rendered in kernel form — requests = the full
  original prose, verbatim; class = the case class recorded
  in the item's own source_pointer locator; producer /
  effects / standing rule / policy facts = the placeholder
  conventions above, since the prose carries no such
  labelled facts.

Verifier result (run on the Thor against the Thor battery
copies, and locally against the repo copies — same output,
results/verify_canonical.log):

    VERIFY PASS (165/165 items: every non-context field
    identical; every context exactly the re-derived
    canonical rendering)

Every non-context field (id, source, order_ts, ts_basis,
gold, operator_correct, correct_outcome,
correctness_evidence, source_pointer) is identical to the
original in all 165 items; item order and counts are
preserved. Content preservation is therefore proven
item-by-item, not asserted. No scoring was run on any set
that had not passed this verifier.

## 4. Scores on the re-expressed sets, and the verdict

Results files: results/canon_{base,patched}_
{heldout_canonical,diagnostic_crossformat}.json

Canonicalised held-out (n=53; correctness subset n=14):

| model | (a) | (b) | answers | non-ALLOW |
|---|---|---|---|---|
| base | 88.68% (47/53) | 64.29% (9/14) | ALLOW 53 | 0 |
| patched r1 | 88.68% (47/53) | 64.29% (9/14) | ALLOW 53 | 0 |

Patched and base are again ITEM-IDENTICAL (53/53), and
item-identical to their own answers on the original
held-out set. Per source (patched): board-shadow (a)
100% (25/25), slice30-booking 100% (12/12), gpu-windows
62.5% (10/16 — the majority-class rate; every answer
ALLOW).

Cross-format diagnostic (n=112; correctness subset n=105):

| model | (a) | (b) | answers |
|---|---|---|---|
| base | 64.29% (72/112) | 59.05% (62/105) | ALLOW 112 |
| patched r1 | 95.54% (107/112) | 92.38% (97/105) | ALLOW 77 / HOLD 35 / DENY 0 |

Against the patched student's original-format diagnostic
(96.43 / 93.33), the held-out-era rendering costs exactly
one net correct item: two answers change, both jev —
e8-jev-003 DENY -> ALLOW (gold HOLD; wrong both ways) and
e8-jev-005 DENY -> ALLOW (gold DENY; correct -> wrong).
Per source (patched, original -> cross-format (a)):
board-shadow 100% -> 100% (all 56 answers ALLOW in both
formats), proof-run + proof-run-2 100% -> 100%,
jev 63.6% -> 54.5%. The crux trio, in cross-format:
e8-board-shadow-018 ALLOW, -025 ALLOW, -033 ALLOW —
unchanged; the operator's error is still learned, not the
policy.

Verdict against CRITERIA.md R1. TRANSFER APPEARS iff, on
canonicalised held-out, patched beats base by >= +10
points on (a) AND answers non-ALLOW on >= 8 of 53 AND (b)
is not below base. Measured:

- (a) gap: 88.68 - 88.68 = **0.0 points** (need >= +10) ✗
- non-ALLOW answers: **0 of 53** (need >= 8) ✗
- (b): 64.29 vs base 64.29 — not below base ✓ (equal)

**TRANSFER DOES NOT APPEAR.** Two of the criterion's three
conjuncts fail at exactly zero — not near the bar. Removing
the held-out era's only renderer novelty (the gpu enrich
insertion) and re-expressing every held-out item in
diagnostic-era formats changed not one answer from either
model. Format eras are therefore NOT the cause of the zero
transfer at any magnitude the criterion can see; per
CRITERIA.md the representation probes follow (section 5),
the door closes as a REPRESENTATION claim, and no patch
round is run by this role.

## 5. Representation probes on the canonicalised data

Adapted from E8's probe code (round1/work/probe.py +
analyze.py + sim2.py, preserved on the Thor). Method:
final hidden states (last position) of the BASE model
under the scorer's exact chat rendering, extracted for the
canonicalised sets by probe_extract.py (batch 16, bf16);
directions built ONLY from the original diagnostic export
(Phase 15's probe.pt), as E8 built them. Files:
probe_heldout_canonical.pt / probe_diag_crossformat.pt on
the Thor; results/probe_results.json, probe_p4.json,
probe_within.json, probe_p6.json here.

Validation of the adaptation (P0): on the original
diagnostic set, the HOLD-minus-ALLOW direction reproduces
E8 exactly — projection AUC 0.9711 (E8: 0.971), ALLOW
projections 17.72 +/- 4.23 (E8: 17.7 +/- 4.2), HOLD
30.74 +/- 3.24 (E8: 30.7 +/- 3.2). The probe pipeline is
the same instrument.

P1 — canonicalised held-out on the diagnostic directions
(u_hold = HOLD mean - global mean; u_deny = DENY mean -
global mean, both from the original diagnostic):
- non-ALLOW (n=6) vs ALLOW (n=47): AUC 0.734 on u_hold,
  0.578 on u_deny. DENY-only vs ALLOW: 0.723 / 0.613.
- Every non-ALLOW item's u_deny projection lies INSIDE the
  ALLOW range: items -35.56 .. -32.37 vs ALLOW
  -40.13 .. -27.06 (mean -34.52 +/- 3.11); margins vs the
  ALLOW mean run -1.05 .. +2.15 — no margin.
- The u_hold signal is source structure, not outcome:
  gpu-windows ALLOW items project HIGHER on u_hold
  (23.92 +/- 0.26) than the gpu non-ALLOW items
  (21.80 .. 23.18).

P5 — within-family (the honest test: gpu-windows is the
only canonicalised held-out family carrying non-ALLOW
golds): gold non-ALLOW (n=6) vs gold ALLOW (n=10) among
gpu items alone —
- AUC on u_hold = **0.000**: every non-ALLOW gpu item
  projects BELOW every ALLOW gpu item. The diagnostic
  HOLD direction anti-separates this family.
- AUC on u_deny = **0.500**: exact chance. The diagnostic
  DENY direction (built on n=3 jev prose items) carries
  nothing about the gpu DENY shapes (feeder-shape /
  fetch-and-execute command shapes under a standing rule).

P2/P3/P4/P6 — the same-seat contention crux, in BOTH
formats (original diagnostic and cross-format diagnostic;
trio = the 3 incumbent-wrong overlaps, correct HOLD;
legal = the 3 correctness-null overlaps on other seats):
- The overlap TEXT is encoded in both formats: overlap vs
  no-contention board AUC on the raw overlap direction
  0.953 (original) / 0.997 (cross-format); on the
  mh-orthogonalised direction 0.957 / 1.000.
- The trio does NOT separate from legal overlaps on that
  direction: trio-minus-legal margin -3.99 (original) /
  -2.08 (cross-format) — the trio projects BELOW the legal
  overlaps; AUC trio vs legal on the orthogonalised
  direction (P4) 0.222 in both formats.
- E8's own orthogonalised contention direction (sim2.py,
  replicated exactly — P6): original trio projects
  5.22 +/- 2.94 vs legal overlaps 5.41 +/- 1.86
  (AUC 0.444) — identical, as E8 reported qualitatively.
  Cross-format: trio -1.59 +/- 0.42 vs legal -3.04 +/-
  1.50 (AUC 0.889 at n=3 vs 3, but the ranges overlap —
  trio -2.08 .. -1.33, legal -4.65 .. -1.68 — and the gap
  is carried by a single legal item, e8-board-shadow-015
  at -4.65; no usable margin).
- The same-seat direction (trio mean - legal mean) is
  board-generic, as E8 found: on it, ordinary no-contention
  board items project 45.18 vs the trio's 45.11 (original;
  E8: 45.28 vs 45.11) and 35.23 vs 36.95 (cross-format) —
  the direction encodes board-ness, not same-seat-ness.
  (The trio-vs-legal AUC of 1.0 on this direction in both
  formats is in-sample circular — the direction is built
  from those same six items — and is NOT evidence of
  separability; the no-contention projections are the
  evidence, and they say the direction does not isolate
  the relation.)

**Relations that remain inseparable, named:**
1. **Same-exclusive-seat contention vs legal overlaps on
   other seats** (the crux trio's deciding relation):
   inseparable in the original format (margin -0.19 on
   E8's own direction; AUC 0.444) and in held-out-era
   format (overlapping ranges, no usable margin). This is
   the relation Phase 15 already indicted; canonicalisation
   does not acquit it.
2. **The gpu-windows DENY relation** (standing-rule DENY
   shapes: feeder-shape and fetch-and-execute command
   shapes, items e8-gpu-windows-003, -004, -007, -012,
   -013 — plus the operator-wrong sentinel -007) vs gpu
   ALLOW: AUC 0.500 on the diagnostic DENY direction,
   within family, after canonicalisation.
3. **The gpu HOLD relation** (the family's single HOLD,
   e8-gpu-windows-011, a network-fetch shape by another
   producer): its projections sit inside the ALLOW cloud
   on both diagnostic directions (u_hold 23.18 vs gpu
   ALLOW 23.92 +/- 0.26; u_deny -35.56 vs ALLOW
   -34.52 +/- 3.11 over all held-out).

## 6. Defects and record corrections found (reported, not silently worked around)

- D1 (record imprecision, Phase 15): SLICE43-E8.md says
  the held-out record "arrives in formats the curriculum
  never showed". At renderer level that is true only of
  the gpu-windows enrich insertion and of the source mix;
  the board and kernel templates are shared verbatim
  across eras (section 2). The zero-transfer explanation
  the record reaches for is therefore weaker than stated —
  and section 4 shows removing the actual format novelty
  changes nothing, so the imprecision does not rescue the
  format hypothesis either.
- D2 (E8 artefact mismatch): EXPLANATION.md reports the
  orthogonalised overlap direction separating overlap
  items at projections ~21.3-21.5 vs no-contention ~15.3,
  trio 21.33 vs legal 21.53. Those scales do NOT reproduce
  from the preserved sim2.py, which yields trio 5.22 /
  legal 5.41 / no-contention mean -0.60 on its
  orthogonalised contention direction (P6a). The 21.x
  figures presumably came from a sim variant that was not
  preserved. The qualitative claim (trio ~= legal) DOES
  replicate exactly; the printed scale does not.
- D3 (my own process): the first backgrounded
  probe_analyze run died with a bare AssertionError and
  produced no results file; two subsequent foreground runs
  exit 0 and agree. Suspected (not proven): a race with
  the preceding extraction writes in the same driver
  chain. All probe numbers above are from the clean runs.
- D4 (inherited battery quirk, not altered — held-out is
  absolute): slice30-booking items 005-012 carry class
  "config" while their requests write booking/... targets;
  that is how Phase 15's curate.py classified them from
  the slice-30 log (s30_class), and the canonicalisation
  copies them byte-for-byte.
- D5 (consistency check, not a defect): gpu-windows item
  ids skip -005 — the item the Phase 15 coordinator
  dropped before any scoring (documented in
  SLICE43-E8.md). Both canonicalised files preserve the
  original id sequences exactly (proven by the verifier).

## 7. Files (this directory, experiments/wsp2/r1/)

- R1-AUTOPSY.md — this report.
- heldout_canonical.jsonl (n=53), diagnostic_crossformat.jsonl
  (n=112) — the re-expressed batteries.
- canonicalise.py — the builder; verify_canonical.py —
  the independent verifier; score_decision.py — the
  Phase 15 scorer, copied unmodified (the scoring path
  used throughout).
- probe_extract.py, probe_analyze.py, probe_p4.py,
  probe_within.py, probe_p6.py — the probe adaptation.
- results/ — every scoring JSON (sanity + canonicalised,
  base + patched), the verifier log, and the probe result
  JSONs (probe_results, probe_p4, probe_within, probe_p6).

Thor-side originals of all runs: ~/wsp-exp16/r1/ (the .pt
hidden-state files stay on the bench; they are large and
regenerable with probe_extract.py).
