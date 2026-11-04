# Slice 43 (part 1) — E2: one patch through the governed lifecycle

Patch v1 (slice 41) was carried through Jacquard's full
lifecycle on a real serving artefact, on the v1.3.0 kernel
(the phase-15 tree rebased over Phase 14's tag). The record
is `experiments/wsp/governance/kernel.jsonl` (90 entries at
E2 close), driven by `governance/govern.py`, a thin
sequencer over `tools/jq.py`. Roles: producer `wsp-patcher`,
senses `wsp-harness` (measurement records), operator = the
coordinator. The serving artefact: `~/wsp-exp/serving/student`
on the Thor, starting as the pristine base (sha256 f47f7117).

## Envelope findings (measured on probe logs first)

- Request verbs must be Tier-E effect primitives (write,
  dispatch, spend, notify, send, schedule, define,
  checkpoint); a first evidence submission using an invented
  verb was REFUSED (FIELD: unknown effect verb) — the
  refusal is a permanent log entry, as it should be.
- Queueing keys on the COMPUTED effects of the requests,
  not the declared list: send/notify/spend queue for a
  non-operator producer; write/dispatch decide instantly.
  A deployment is honestly a `send` (the patched weights
  are transmitted into the serving slot) plus a `write`;
  declared `irreversible` rides as a class marker.
- An approved queued proposal executes its effects in the
  record at decision time (replay shows `execution: applied
  write, send`); `jq execute` serves the separate sandbox
  action profile and correctly reports nothing pending here.

## The lifecycle, as recorded

1. Evidence (senses): the E1+E4 verdict bundle entered by
   hash (bundle sha256 cd808750) — validation 83.5 -> 91.5,
   heldout 80.5 -> 85.0, forgetting unmoved, ablation
   exact. Decided allow on submission.
2. Shadow: proposal wsp-shadow-v1 QUEUED
   (reason: protected-effect:send), operator approval
   bound to hash 60f58b58, execution applied, closed.
   Physical act: patched copy placed BESIDE serving
   (serving/student-shadow); fresh validation run from
   the serving area = 0.915 — reproduces E1. Serving
   artefact untouched. Evidence entered by hash.
3. Canary: proposal queued, approved, closed. Physical
   act: serving/student replaced by the patched model
   (weights sha256 14ea88d0, the sealed patch output);
   fresh held-out run ON THE SERVING ARTEFACT = 0.850 —
   reproduces E1. Evidence entered by hash.
4. Adopt: proposal queued, approved, closed. Adoption
   rests on the recorded chain: verdicts + ablation (e1),
   shadow reproduction, canary reproduction. Serving
   state attested by hash in the adoption evidence.
5. Rollback: proposal queued, approved, closed. Physical
   act: serving/student restored from the gated pristine
   copy — sha256 = f47f7117 and `cmp` against the gated
   original clean: BIT-FOR-BIT restoration, proven, and
   the proof entered as evidence.

Replays of the adopt and rollback proposals answer "why
was this allowed" from the log alone: every decision is
hash-bound to its proposal, and every proposal's evidence
chain is in the same log.

## Governance cost

4 deployment proposals, 4 operator decisions (all
approve, each on recorded evidence), 6 evidence
submissions (1 refused, above). End-to-end ≈ 25 minutes
of coordinator time, dominated by the two fresh scoring
runs the evidence required (~70 s of GPU); the kernel
interactions themselves total seconds. For scale, the
patch artefact itself cost ~14 minutes of patcher time
plus ~15 minutes of E1/E4 measurement. Governance added
four decisions and a few minutes — and bought a complete
replayable record, hash-bound stages, and a proven undo.

## What E2 does and does not prove

Proves: the rails carry a real weight artefact through
eval -> shadow -> canary -> adopt -> rollback with
evidence at every gate and a bit-for-bit undo.
Does not prove: multi-operator operation; automated
evidence production (receipts were coordinator-run);
or that the queue catches a bad patch — the operator is
the check; the record makes the check accountable.
E6 stress-tests the same rails with repeated rounds.
