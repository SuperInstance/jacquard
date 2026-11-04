# R4 battery — the elephant PanicDial joint (calm / alarmed / stampede)

Built 2026-11-04 by the R4 battery-builder seat for Jacquard
Phase 16, slice 46 part R4. Labels by construction only. No
model was patched in the making of this battery; the incumbent
and the student were run only after the battery was frozen and
verified, as baselines. The held-out split is the governed
split for the later patch rounds: **held-out items must never
be shown to any patcher** (PATCH-PROTOCOL rules); patchers see
diagnostic items and validation aggregates only.

## What is being measured

`PanicDial.read(room)` (see R4-INVENTORY.md) maps a room to
[0 calm .. 1 trampling] by equally-weighted substring lexicon
hits, trailing-30 s density and alarm-gated ripple. The joint
under study is that weighting. This battery is the narrow set
for coaching it: 3-way classification (calm / alarmed /
stampede) of short room transcripts, labels by construction.

Class form for the incumbent: fixed equal-thirds thresholds on
its [0,1] reading (< 1/3 calm, < 2/3 alarmed, else stampede),
stated in advance, untuned — the E7 treatment.

## Files

| file | what |
|---|---|
| `gen_battery.py` | deterministic (seeded) generator; writes all three splits |
| `diagnostic.jsonl` | 120 items, ids `r4diag-001`…`r4diag-120` — patcher-visible |
| `validation.jsonl` | 60 items, ids `r4val-001`…`r4val-060` — aggregates only |
| `heldout.jsonl` | 120 items, ids `r4held-001`…`r4held-120` — GOVERNED, never shown to patchers |
| `verify_battery.py` | independent checks incl. gold recomputation from construction parameters |
| `run_incumbent.py` | builds real Rooms, runs the real PanicDial (elephant checkout), equal-thirds classes |
| `score_student.py` | Qwen3-0.6B zero-shot scorer (Thor), fixed prompt |
| `defect_scan.py` | quantifies the R4-INVENTORY defects over the battery texts |
| `results/*.json` | per-item baseline outputs for both baselines, all splits |

Item schema: `{"id", "split", "label", "subtype", "boundary",
"construction": {...}, "messages": [{"author", "text",
"ts" (seconds, relative to first message), "reactions"
({name: count}), "n_replies"}]}`. `boundary: true` marks
subtypes designed to sit near the joint's decision boundary;
it is construction metadata, not a difficulty guarantee.

## Gold construction rules (written BEFORE generation)

Every item is generated from construction parameters, and the
gold label is a function of those parameters alone — never of
the text's lexicon hits, the incumbent's reading, or any model
output. The verifier (`verify_battery.py`) carries its own
copy of this function and recomputes every gold from the
stored parameters; a mismatch fails the battery.

Parameters per item:

- `genuine` (bool): a real danger to people or property is in
  force in the room's world during the transcript — not
  negated, not resolved, not quoted/fictional, not a scheduled
  drill or test, not metaphorical/polysemous use.
- `corroborators` (int): number of distinct authors, other
  than the first reporter, who independently confirm or
  escalate the genuine danger.
- `roomwide_action` (bool): an in-earnest room-wide immediate
  action call is in force (evacuate / abandon / muster / mayday
  relay acted on), issued or echoed by the room, not by one
  voice alone.
- `minor` (bool): the genuine incident is minor and contained
  (small contained leak, minor injury, smell being checked).

Gold function:

    if not genuine:                       -> calm
    elif roomwide_action or corroborators >= 3: -> stampede
    else:                                 -> alarmed

Rationale, stated once: a room is *calm* when no genuine
danger is in force, whatever words are flying; *alarmed* when
genuine danger is present but local — a first report, a minor
contained incident, a slow-developing risk — without room-wide
mobilisation; *stampede* ("trampling") when genuine danger has
become the whole room's immediate business: corroborated by at
least three further authors or driving a room-wide action.

## Subtypes (18; identical subtype shape in every split,
templates and content disjoint per split — see Split design)

calm (gold by `genuine=false`):
- `everyday_chat` — routine talk, logistics, small talk. Core.
- `work_routine` — maintenance/inventory/rota talk. Core.
- `trivia_burst` (boundary) — rapid-fire quiz/joke/laughter
  burst: density-spike trap, no danger.
- `surprise_urgency` (boundary) — urgency words in earnest but
  harmless haste (surprise party, gift, cake, guest arrival).
- `drill_notice` (boundary) — scheduled drill / alarm test /
  safety-briefing notice: alarm words, future and planned.
- `fiction_discussion` (boundary) — film/book/game discussion
  quoting alarm-laden plot events.
- `negated_alarm` (boundary) — alarm raised and stood down in
  the room: "false alarm", "no fire", all-clear given.
- `polysemy_calm` (boundary) — alarm lexemes in other senses:
  crash (software/market), run (errands/print run), flood (of
  emails), leak (news), fire (a stove lit deliberately, a kiln).

alarmed (gold by `genuine=true`, `corroborators<=2`, no
room-wide action):
- `first_report` — one author reports smoke/smell/water where
  it should not be; others ask or acknowledge. Core.
- `minor_incident` (`minor=true`) — minor injury, small
  contained spill/leak, minor bump; being handled locally.
- `slow_burn_technical` (boundary) — genuine worsening risk in
  technical language with few or no lexicon words (levels,
  readings, pressures, list angle), measured tone, slow tempo.
- `single_loud_voice` (boundary) — one author repeats the
  alarm loudly with heavy reactions; it is genuine but
  uncorroborated and no room-wide action follows: ripple trap.
- `weather_warning` — official worsening-weather warning
  relayed; preparation talk, no immediate danger in the room.
- `uncertain_signal` — an alarm/detector is sounding, cause
  unknown, someone is checking: genuine possibility, unresolved.

stampede (gold by `genuine=true` and (`corroborators>=3` or
`roomwide_action=true`)):
- `confirmed_spread` — fire/flood confirmed by several authors
  and spreading; evacuation begins. Core.
- `fast_water` — water rising fast in several places at once;
  several authors; abandon/muster preparations.
- `impact_event` — collision / capsize / person overboard;
  mayday relayed and acted on by several authors.
- `evacuation_underway` — room-wide evacuation in progress:
  all-hands action calls from several authors, muster counts.
- `technical_cascade` (boundary) — room-wide immediate action
  over a genuine casualty described mostly in technical words
  (list, bulkhead, pressure, taking water), few lexicon hits.
- `escalating_cascade` (boundary) — starts as one report, then
  corroboration accelerates inside the transcript until the
  room is mobilised: tempo trap in both directions.

## Split design

- diagnostic: harbour / ferry / boathouse / fish-market world.
- validation: community hall / library / school-theatre world.
- held-out: alpine hostel / bakery depot / campsite world.

The pools share no people names, place names, object
vocabularies or sentence frames. Generation is slot-filling
from per-split scene kits with fixed per-split seeds
(diag 20261146, val 460046, held 77114611); re-running
`gen_battery.py` reproduces all three JSONL files
byte-identically (verified across runs).

Sizes and balance (verifier-enforced): diagnostic 120 =
40/40/40 calm/alarmed/stampede; held-out 120 = 40/40/40;
validation 60 = 20/20/20. Messages per item: 3–12. Boundary
share target ~40% per split (verifier reports the exact counts).

Cross-split leakage screen (verifier-enforced): no exact or
normalised-text duplicate item text within or across splits;
cross-split near-duplicate screen = token Jaccard over each
item's full concatenated message text, all diagnostic×held-out,
diagnostic×validation and validation×held-out pairs; the
maximum is reported and must be < 0.60.

## Fixed student prompt (stated in advance)

The student (fresh Qwen3-0.6B base, zero-shot, greedy) sees
each item rendered exactly as:

    Classify the room's alarm state as calm, alarmed, or
    stampede. Answer with just the label.

    Transcript:
    [+0s] <author>: <text>
    [+12s] <author>: <text> (reactions: 3, replies: 1)
    ...

The `(reactions: N, replies: M)` suffix appears only when the
message's total reaction heat or reply count is non-zero, so
the student receives every signal the incumbent reads (text,
relative timing, reaction heat, reply count) in text form.
Predicted label = first word-boundary occurrence of
calm|alarmed|stampede in the raw output; none = wrong.

## Baseline results

(Filled after the frozen battery was verified; see
`results/` for per-item outputs. Numbers are recomputed from
those files by the coordinator-standard scripts in this
directory.)

- Incumbent PanicDial (equal-thirds): TBD
- Student Qwen3-0.6B (zero-shot, fixed prompt): TBD

## Weaknesses (stated by the builder)

- Labels are construction golds for a *semantic* reading of a
  room; the gold function deliberately makes corroboration and
  room-wide action the stampede boundary. A reasonable reader
  could place a lone confirmed fire at stampede; the battery's
  stated rule places it at alarmed (genuine, uncorroborated).
  The rule is pre-stated and uniformly applied, which is what
  makes the joint coachable against it — but it is a rule, not
  a law of nature.
- Transcripts are templated, not harvested from real rooms:
  elephant ships no labelled room corpus, and harvesting chat
  logs would raise consent/provenance problems this slice does
  not need. Surface diversity is therefore bounded by the
  scene kits; the held-out pool tests frame-level, not
  world-level, generalisation.
- Reaction/reply counts are authored construction parameters,
  rendered identically to the incumbent (heat, stub replies)
  and to the student (text suffix); real rooms carry richer
  reaction semantics the dial also cannot read.
