# Slice 28 — the expensive class: inventory, shadow, and the honesty gate

Phase 10, slice 28. Charter: inventory the Thor's real
GPU-heavy flows from records, name the class whose single
jobs run ≥ ~5 GPU-minutes with real submissions behind it,
shadow-score the v2 consumption policy over it, then run a
bounded live window with the policy ACTIVE for that class
only — **or, if no such class genuinely flows, manufacture
nothing** and deliver the machinery ready with the verdict
stated plainly.

## The inventory (from records, 2026-11-03)

Method: `docs/slice28/inventory.py`, run read-only on the
Thor against every store on the box that records submitted
GPU work; raw output at `docs/slice28/inventory.json`. The
gpu-queue is, by the standing design since 2026-10-27, the
Thor's only dispatch path for submitted GPU jobs — its
history is the population, not a sample. (Bench lanes such
as casting-call ran as agent-driven serves, not submitted
jobs; they keep no job records with GPU durations on this
box, and a serve is not a submission a queue policy can
price.)

| class | submissions | median | max | ≥ 300 s | total GPU time |
|---|---|---|---|---|---|
| gpuq `foundry-loop` (feeder mints) | 1,637 done | 40.1 s | 180.3 s | **0** | 1,096.7 min |
| gpuq `jacquard` (windows 1+2 benches) | 12 (10 done, 1 failed, 1 queued) | 20.1 s | 20.1 s | **0** | 3.4 min |
| image studio (gallery: 60 images, 49 jobs) | 49 jobs | seconds (SDXL base measured 13.7 s cold / 11.8 s warm at build) | — | **0** | — |
| foundry portal builds | 28 versions, ever | — | 265.3 s wall, of which **0.16 s GPU** | **0** | — |

The foundry portal's longest build is the only record on
the box that even approaches five minutes, and its time is
cloud-brain and preview wall time; its GPU content is a
sixth of a second. Every image-studio model present is a
distilled/turbo variant generating in seconds. In the
gpu-queue's complete history — 1,647 finished jobs — the
single longest run is 180.3 s, and exactly one job exceeds
120 s.

**Verdict: no job class on the Thor runs ≥ ~5 GPU-minutes
with real submissions behind it. The honesty gate fires.
There is no live window in this slice, and none was
manufactured.**

## Shadow over the only voluminous class (foundry-loop)

The feeder class is the one class with volume, so it is
shadow-scored — at class level, and labelled as such: the
feeder never declared per-job outputs/uses into a Jacquard
log, so a strictly causal per-submission replay is not
reconstructable; what the records do support exactly is
the class's consumption ratio and the policy's verdict
robustness. From the foundry registry: **16,667 assets,
39 ever used — a lifetime ratio of 23 bp** against the
policy's 5000 bp threshold. Under v2, the exemption budget
(3 completed outputs) is spent inside the first family
job (8 assets); every subsequent feeder submission prices
at a ratio that — even crediting all 39 eventual uses as
early as the record could possibly allow — never comes
within two orders of magnitude of the threshold. ≈ 1,636
of 1,637 feeder jobs would have been held, putting
≈ **1,096 GPU-minutes (≈ 18.3 GPU-hours)** in front of an
operator.

That number prices the disease, and it validates the
existing cure rather than prescribing a new one: 1,636
batched holds on a homogeneous class is not supervision,
it is a second job. The correct act for a class at 23 bp
is a class-level standing decision — which is exactly
what Casey's ruling 6 already is (feeder OFF; the
inventory confirms `feeder.enabled: false` today). The
consumption policy's proper theatre is the margin — a
mixed class where some production is used and some is
not — and on this box, today, no such class runs long
jobs. Both halves of that sentence are measurements, not
impressions.

## The machinery, ready (what activation takes)

The v2 gate is built into the bridge, configured as data
in a log's policy record — never as a code constant — and
covered by `tests/test_consumption_gate.py` (5 tests:
budget claims recorded then a hold at ratio 0; the held
job never reaches gpuq; budgets are per-producer;
completed consumption restoring passage at exactly the
threshold; the refinement flag exempting a consumer;
and, with no gate configured, behaviour byte-for-byte the
pre-gate bridge). The same `adapters/consumption.py`
prices the shadow and the gate.

Activation, when a qualifying class exists, is one init
line on a new governed log:

```
python3 tools/jqgpu.py --log LOG init --window '{...}' \
  --consumption-gate '{"job_class": "gpu-heavy",
    "threshold_bp": 5000, "exemption_budget": 3,
    "exempt_self_consuming": true}'
python3 tools/jqgpu.py --log LOG submit --producer P \
  --name N --cmd CMD --output ART --class gpu-heavy
```

`exempt_self_consuming` is recommended for live use: the
raw rule holds consumers too (slice 27's bench-7 row is
the receipt), and a live gate should not tax the demand
side it exists to protect; the flag defaults off so the
shadow semantics stay the reference. The exchange rate a
future window must state before opening, per this
inventory: the class's median job must be worth ≥ ~5
operator-minutes of GPU time per hold at the observed
hold rate — on today's records no class qualifies, and
the plausible candidates that could become one (full-
quality image-generation batches; final-quality render
jobs; training/eval runs submitted as jobs rather than
serves) are named here so a future coordinator can check
the records again instead of re-deriving this section.

## Defect found in passing (fixed here, recorded)

Wiring the gate exposed a seam defect: the rule hook
receives a proposal's *requests* only, and a submission's
declared `uses` rode only on the proposal body — so the
refinement (exempt self-consuming submissions) was
unpriceable live, however correct the shadow arithmetic.
Fix: `submit_job` now carries declared uses on the
dispatch request as well (body-level list remains the
canonical record the projections read). Non-consuming
proposals are byte-identical to the windows 1+2 form.
Covered by the gate battery's refinement test, which
failed before the fix and passes after.
