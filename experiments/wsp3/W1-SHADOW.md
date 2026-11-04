# W1 shadow — the two grown dial specialists vs real fleet traffic

Phase 17 W1, per experiments/wsp3/CRITERIA.md (pre-stated,
hash-bound before any run). Corpus: experiments/wsp3/
W1-CORPUS.md (156 real agent-inbox messages, full git
history, content-deduplicated). This is the brief's named
substitute for live traffic — no live dial consumers exist
in the fleet — and it is labelled a substitution here and
everywhere these numbers are used.

All agreement numbers below are specialist-vs-INCUMBENT on
the 91 corpus items both specialists could score (prompt
<= 8,192 tokens; the 65 too-long items carry incumbent
readings only, in scores.jsonl). Agreement with the
incumbent is not accuracy. Accuracy enters only through
the blind teacher spot-check, which is a separate grader's
work — see the pending section at the end.

## Artefacts, verified before use

- Model/code specialist (E7 round 1, ADOPTED): Thor
  ~/wsp-exp/e7/round1/patched-r1 — config.json,
  model.safetensors, tokenizer files all present. Scored
  with the phase's own ~/wsp-exp/e7/score_joint.py,
  unmodified.
- Panic specialist (R4 round 1, ADOPTED): Thor
  ~/wsp-exp16/r4/round1/patched — present, same file set.
  Scored with the phase's own ~/wsp-exp16/r4/
  score_student.py, unmodified (execution was chunked —
  see Operational record; the harness, prompt, decoding
  and extraction are untouched).
- Model/code incumbent: signal_chain_dial.py from
  SuperInstance/signal-chain @f113fbf; the Thor clone's
  md5 (0daa4a4b0ea1b69b7863567c368d61ec) matches the
  Oracle read clone ~/sigchain-read exactly. Class
  mapping = E7 baseline_joint.py equal thirds of [-1,+1].
- Panic incumbent: the real elephant PanicDial imported
  from the R4 sparse checkout ~/wsp-exp16/r4/elephant-src
  (elephant @44e7363, per R4-INVENTORY.md). Class mapping
  = R4 run_incumbent.py equal thirds of [0,1].
- Battery reference numbers (from the phase records):
  E7 specialist held-out 84.2% (incumbent dial 46.7%);
  R4 specialist held-out 50.8% (incumbent dial 15.0%,
  zero-shot student 32.5%). Both batteries are balanced
  40/40/40 by construction. Live traffic is not.

## The adaptation the panic dial required

Corpus items are individual messages; the panic dial
reads ROOMS. Each item was therefore read as a
single-message room (author "agent", ts 0, no reactions,
no replies — the corpus carries none), for the incumbent
and, rendered through R4's own render_transcript, for
the specialist. Consequence, stated plainly: the dial's
density term (needs >= 2 messages in the trailing
window) and ripple term (needs reactions/replies) are
identically zero in this adaptation, so the incumbent's
reading is 0.40*alarm_norm + 0.25*urgency_norm only, with
a hard ceiling of 0.65 — below the 2/3 stampede line.
The room dynamics the dial was built to read are absent
from this traffic substitute; that is the substitute's
main structural limitation, and it binds the incumbent,
not the specialist (the specialist reads the text).

## Live agreement — model/code dial (n=91 eligible)

Overall: **66/91 = 72.5%** (all 91 specialist outputs
parseable).

Confusion, incumbent -> specialist:

| incumbent | code | mixed | model | n |
|---|---|---|---|---|
| code  | 66 | 21 | 1 | 88 |
| mixed | 2  | 0  | 0 | 2  |
| model | 1  | 0  | 0 | 1  |

Per incumbent class (share the specialist matches):
code 66/88 (75.0%), mixed 0/2, model 0/1 — the mixed and
model denominators are 2 and 1 because the incumbent
itself almost never says them on this traffic (full
corpus: code 153, mixed 2, model 1 of 156).

Per specialist class: of the specialist's 69 code calls,
66 match the incumbent; of its 21 mixed calls, 0 match
(every one is an item the incumbent called code); its
single model call is an incumbent-code item.

Sensitivity: agreement is 9/11 (81.8%) on eligible
prospector-log items and 57/80 (71.3%) on everything
else — the headline is not one log agreeing with itself.

## Live agreement — panic dial (n=91 eligible)

Overall: **71/91 = 78.0%**, counting the specialist's 6
unparseable outputs as disagreements (the phase
harnesses' convention: no label extracted = wrong).
Parseable-only: 71/85 = 83.5%.

Confusion, incumbent -> specialist: the incumbent calls
all 91 eligible items calm (and all 156 corpus items —
its highest reading anywhere in the corpus is 0.2354,
below even the 1/3 alarmed line). The specialist answers:
**calm 71, alarmed 11, stampede 3, no label 6.**

Sensitivity: prospector-log items 8/11 (72.7%),
everything else 63/80 (78.8%).

## Per-class behaviour in the wild

- **mixed is alive for the specialist, dead for the
  incumbent.** The E7 specialist calls 21/91 items
  (23.1%) mixed — the class it was coached to recover
  (battery held-out mixed 75% vs the incumbent's 7.5%).
  The incumbent calls 2/156 items mixed in the wild.
  Whether the specialist's 21 wild mixed calls are RIGHT
  is exactly what the blind spot-check measures; what
  shadow alone establishes is that the class survived
  contact as a behaviour: the specialist still uses it,
  at volume, on real traffic.
- **model is dead for both** (incumbent 1/156, specialist
  1/91). On the battery this class was 40/120 by
  construction; in the wild, agent traffic that reads as
  pure model prose barely exists — or neither instrument
  can see it. Shadow cannot separate those two readings.
- **stampede is alive for the specialist, impossible
  for the incumbent here.** The specialist calls stampede
  on 3 items (c0021, c0044, c0113 — all ordinary task/
  result traffic, none of them prospector-log) and
  alarmed on 11 more. The incumbent, in the
  single-message-room adaptation, cannot reach stampede
  (ceiling 0.65 < 2/3) and in fact reaches nothing:
  calm 156/156. The R4 battery's central incumbent
  defect — "the dial never once predicts stampede" —
  is total on this traffic.
- **The panic incumbent is a single-class instrument
  in the wild.** Mechanism: alarm_norm divides distinct
  alarm hits by word_count/40; on documents of ~1,000+
  words the term cannot lift the reading, and the two
  room terms are zeroed by the adaptation. Its battery
  held-out was 15.0%; on live traffic its class output
  carries no information at all (one class, always).
- **The model/code incumbent is also near-single-class
  in the wild, in the opposite corner:** code 153/156.
  Mechanism (in the _score source): lexicon hits count
  DISTINCT words and saturate with length, while the
  code-symbol count grows with every character, so long
  documents tip to code regardless of content. The
  dial's battery behaviour (46.7% held-out, mixed
  nearly invisible) and its wild behaviour are the same
  instrument at two length scales.

## Drift against the battery numbers

The battery accuracies (84.2 / 50.8) were measured
against construction labels on balanced classes. The
live numbers above are agreements with the incumbent
on a class mix that is nothing like 40/40/40: under the
incumbents, live traffic is 98% code and 100% calm.
Two consequences, both stated in CRITERIA's spirit:

1. High live agreement is cheap here. A specialist that
   always said "code" would agree with the model/code
   incumbent 88/91 (96.7%); one that always said "calm"
   would agree with the panic incumbent 91/91. The
   measured agreements (72.5%, 78.0%) are BELOW those
   degenerate baselines — the specialists are not
   collapsing to the incumbent's majority class; they
   spend their disagreement exactly on the classes the
   incumbent cannot see (mixed 21, alarmed 11,
   stampede 3). Whether that spend is signal or noise
   is the grader's call, not shadow's.
2. The class-mix caveat cuts the other way for the
   incumbents: their wild class collapse means the
   SURVIVES CONTACT bars (grader agreement within 10
   points of 84.2 / 50.8, no battery-alive class at
   recall 0) will be decided on the rare classes, where
   the sample deliberately over-represents what the
   incumbent missed.

## Operational record (deficits, stated)

- The R4 scorer was killed by SIGTERM (exit 143) three
  times as a long run — twice under nohup, once inside
  tmux — each time during generation, with no traceback
  and no journal/oomd trace found (systemd-oomd is
  inactive on the box). The E7 scorer, run earlier the
  same day as one long process, was not killed. On a
  byte-balanced 6-way split, the two small chunks
  (4 and 2 items) completed and the four larger ones
  were killed. Scoring was finished as 16 micro-chunk
  runs of 6 items with per-chunk retries (one chunk
  needed 3 attempts); all 91 items scored by the
  unmodified harness. Cause unknown; the box is heavily
  shared (other agents' workloads resident throughout).
  File this as an environment defect of the run, not a
  property of the specialist.
- The Oracle's root disk was at 100% (0 bytes free)
  when this lane started; the repo work ran in /tmp
  (tmpfs) and the branch was pushed from there. The
  coordinator's phase17-practice branch was at that
  point local-only on the Oracle (it has since been
  pushed); p17-w1 is based on its commit 5a38316.
- Long ssh sessions to both boxes die at ~5 minutes
  (proxy broken pipe); all monitoring was done with
  short calls and on-box detached execution.

## Teacher spot-check — PENDING BLIND GRADER

This section is filled by the coordinator from the
blind grader's labels. The builder did not grade.

Sample: blind_sample.jsonl, 66 items, id + text only.
Drawn from the 91 items both specialists scored,
stratified by the model/code incumbent's class with
rare strata exhausted (incumbent mix in sample:
code 63, mixed 2, model 1) and, inside the dominant
stratum, every panic-specialist alarmed (11) and
stampede (3) call force-included so the stampede
watch is measurable. Sample specialist mixes:
model/code {code 55, mixed 11, model 0}; panic
{calm 46, alarmed 11, stampede 3, none 6}.

To be reported by the grader/coordinator:
- specialist and incumbent agreement with the grader,
  per class, for both dials;
- panic specialist stampede recall on the sample
  (CRITERIA: reported by name, whatever it is);
- SURVIVES CONTACT verdicts per dial (grader agreement
  within 10 points of battery held-out — model/code
  >= 74.2, panic >= 40.8 — AND no class at recall 0
  that was alive on the battery);
- re-coaching trigger check (>= 15 points below
  battery held-out, or a battery-alive class at
  recall 0 in the wild).

## Files

- corpus.jsonl.gz + build_corpus.py — the corpus and
  its deterministic generator (W1-CORPUS.md).
- scores.jsonl — per item, per architecture: incumbent
  reading + class, specialist class + raw output (or
  null + note for the 65 too-long items).
- blind_sample.jsonl — the grader's sample (id + text).
- governance/evidence-p17-w1-shadow.json — the stage
  evidence record for the coordinator to enter.
