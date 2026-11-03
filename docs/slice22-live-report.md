# Slice 22 live report — Jacquard governs the Thor's gpu-queue (2026-11-02)

Beachhead 3, live: real job submissions to the Thor's GPU
queue were governed end-to-end by Jacquard — proposal →
kernel decision → (only for allowed jobs) dispatch to the
incumbent `gpuq` → outcome journalled back into the kernel
log — inside the booked Thor window 2026-11-03 01:15–05:00
UTC (lane `jacquard-build` on the schedule board). All
numbers below re-derive from the committed live log
(`docs/slice22/kernel.jsonl`, 91 entries, chain verified)
and the gpuq record on the Thor.

## The governed setup (stated in the log before going live)

The live kernel log is a NEW log (own genesis, own log_id
`9cbf80c8e820d49a10da9d92b0f18d2770b48d562c816436628c881d14abaff1`),
canonical home `/home/ubuntu/jacquard-gpu-live/kernel.jsonl`
on the Oracle. Its genesis carries a `gpu-policy-record`
sense entry stating, before the first live dispatch:

- governed namespace: the gpuq lane **`jacquard`**;
- job class: **`gpu-bench`** — short, finite GPU
  bench/inference jobs through the bridge, each declaring
  one output artifact under `~/jacquard-gpu-live/` on the
  Thor. Chosen because a small torch matmul bench in the
  Thor's `~/ml/.venv` (torch 2.11.0, CUDA verified) runs in
  well under a minute and produces a real, consumable
  result file; no service was started or touched;
- policy (`gpu-bridge-policy/1`, data in
  `adapters/gpu_queue.py`, applied through the kernel's
  rule hook): ALLOW known producers with no denied/held
  shape; HOLD network-fetch shapes and unknown producers
  for a batched hash-bound operator decision; DENY feeder
  shapes and fetch-and-execute shapes by shape, reason
  recorded;
- window: 7 governed submissions targeted (8 landed — see
  the sentinel finding), inside the booked window.

**Thor route (verified, with a finding).** Dispatches ran
over the Thor's existing SSH door from the operator VM
(`ssh -F ~/workspace/ssh/thor.config thor`, ProxyJump via
the Oracle to tunnel slot 2225; that VM's key is authorised
on the Thor). From the Oracle itself, every key it holds
was denied by the Thor — no Oracle key is authorised there,
and adding one would be a persistent Thor-side change the
constraints forbid. Bridge invocations therefore executed
on the operator VM as fresh processes, and after **every**
invocation the log + journal were copied to their canonical
Oracle path with sha256 equality checked (final log sha256
`a0fa08c752de43c515ba9f8ec09fa26605d56e65f8cb9cc059a101fb06efd4a2`).
The transport is configuration (`JACQUARD_GPU_THOR_CMD`),
not code. **Zero new persistent processes or services on
the Thor; nothing installed on the Thor.** Removing the
adapter restores the incumbent path exactly, and other
lanes' direct gpuq use was never touched.

## Counts (from the live log, `tools/jqgpu.py counts`)

| | |
|---|---|
| submitted | **8** |
| allowed at submission | **4** (bench-1, bench-2, bench-3, sentinel v2) |
| held at submission | **1** (held-1, unknown producer) → released by operator → dispatched |
| denied | **3** (feeder shape, fetch-and-execute, sentinel v1 false positive) |
| dispatched to gpuq | **5** (job-3…job-7) |
| completed (gpuq done, exit 0, kernel-confirmed) | **4** |
| failed | **0** |
| still queued in gpuq at close | **1** (the sentinel, by design) |

## The jobs

| gpuq id | name | kernel story | gpuq outcome | artifact (Thor) |
|---|---|---|---|---|
| job-3 | jacquard-bench-1 | allow → dispatch | done, exit 0 | `bench-1.json` — sum 25602.857421875, device "NVIDIA Thor" |
| job-4 | jacquard-bench-2 | allow → dispatch | done, exit 0 | `bench-2.json` |
| job-5 | jacquard-held-1 | HOLD (unknown producer `mystery-lane`) → operator release (hash-bound, `tools/jq.py decide approve`, binding `9a77f702…`) → dispatch | done, exit 0 | `held-1.json` |
| job-6 | jacquard-bench-3 | allow → dispatch, declared `uses: [gpu-artifact:bench-1]` | done, exit 0 | `bench-3.json` — embeds `consumed_sum: 25602.857421875`, bench-1's exact sum |
| job-7 | jacquard-sentinel | allow (v2) → dispatch | **queued** at close | none (never ran) |

The chain respected gpuq's successor rule throughout: each
job had the next queued behind it; the daemon's transient
no-successor hold was recorded against lane `jacquard`
(job-4, 16:39:02-0900) and cleared as the chain advanced.
The sentinel is the declared last job: with the feeder OFF
it stays queued in gpuq — the honest end-state, stated in
advance in the policy record.

## Acceptance evidence

- **Real jobs end-to-end.** Proposal, decision, execution,
  dispatch (bridge journal, `docs/slice22/kernel.jsonl.gpu-journal.jsonl`),
  and outcome (action confirm transitions + `gpu-outcome`
  sense entries) are all in the log; gpuq's own record
  (job-3…job-6 done/exit 0, job logs `job-{3,4,5,6}-*.log`)
  agrees.
- **DENIED jobs provably never reached gpuq (two-sided).**
  Kernel side: decision entries with outcome `deny` and
  `gpu-policy` sense entries naming the reasons
  (`feeder-shape: …`, `fetch-and-execute: …`). gpuq side:
  `gpuq list` contains no `jacquard-feeder-on` and no
  `jacquard-fetch-exec` job, and `gpuq status` showed
  `feeder: OFF` after the feeder-shaped submission — the
  denied command was the one that would have turned it on.
- **HELD job dispatched only after release.** Before
  release: the item sat in the kernel decision queue
  (binding `9a77f702…06b38`) and `gpuq list` had no
  `jacquard-held-1`; bridge dispatch scans executions, and
  a queued proposal has none. After the hash-bound release:
  dispatched as job-5.
- **Duplicate dispatch (idempotency).** The bridge's
  `dispatch` verb ran after every submission (7+ times);
  each action re-reported its recorded gpuq job id and was
  never re-added: gpuq holds exactly 5 jacquard jobs, one
  per allowed action. A final explicit dispatch after all
  outcomes were polled added nothing.
- **Senses live.** Published over the live log at close:
  `queue-depth`, `output-use:jacquard-build`,
  `output-use:operator`, and **`gpu-downstream-use`** — the
  C3 churn question as a live sense, method stated in the
  entry: of the **4** completed governed jobs' declared
  outputs, **1 was used** (`gpu-artifact:bench-1`, consumed
  by bench-3, whose artifact embeds bench-1's exact sum),
  **3 unused** (bench-2, held-1, bench-3 outputs) —
  ratio 2500 bp. Honest both ways: a true positive and true
  negatives.
- **Anchoring.** The live log joined the anchoring cadence
  in SuperInstance/jacquard-anchors under its own log_id:
  checkpoint seq 0 `gpu-live-window-open` at length 8
  (anchors commit `bbc41c6`), seq 1 `gpu-live-window-close`
  at length 91 (commit `4b339e9`), both signed by the
  successor key `ce805efd…f5072`. Verification from the
  Oracle copy: `verified`, anchored 91/91, tail 0.
  **Blocker recorded:** registry-schedule verification
  (`jqanchor verify --keys`) cannot schedule this log —
  `schedule_from_registry` raises "key registry windows for
  log 9cbf80c8… do not partition its checkpoint sequence
  (gap or overlap after seq None)", because keys.json gives
  both keys a default window from seq 0 for any log_id
  without an explicit entry. A log born after the rotation
  is signed only by the successor, so single-key
  verification (`--pubkey ce805efd…f5072`) is the correct
  schedule today; the registry format needs a per-log
  "born under key K" entry to express it. Recorded here
  rather than forced.

## Disagreements with the incumbent path, classified

- **Jacquard wrong: 1.** The first sentinel submission was
  DENIED as a feeder shape because its command's prose note
  mentioned gpuq and the feeder ("stays queued in gpuq …
  feeder OFF") and the bridge's feeder regex matched any
  `gpuq … feeder` text. The denial stands in the live log
  (it happened; the record is the record). The shape was
  tightened to require `feeder` in gpuq's subcommand
  position (commit `e84e4fe`, regression test added), and
  the resubmitted sentinel was allowed and dispatched.
  This is why the window shows 8 submissions for a
  7-submission target.
- **Incumbent wrong: 0.** gpuq behaved exactly per its
  stated rules throughout, including its successor holds.
- **Policy gaps: 2.** (1) The anchor-registry partition
  gap above (slice-21 tooling, surfaced by the first
  second log_id). (2) Bridge shape policy reads command
  text: the subcommand-position fix removes the observed
  false positive, but prose/code ambiguity in shell text
  is a residual risk of any text shape — named, not
  hidden.

## Thor-side actions taken (complete list)

Read-only: `gpuq status`, `gpuq list`, reading `gpuq`,
`daemon.py`, `queue.json`, `status.json`; one torch
availability probe (`~/ml/.venv/bin/python -c 'import
torch…cuda.is_available()'`, no job). Via the bridge only:
five `gpuq add` calls (job-3…job-7, lane `jacquard`).
Created by gpuq/the jobs themselves: queue entries and job
logs for job-3…job-7; output artifacts
`~/jacquard-gpu-live/{bench-1,bench-2,held-1,bench-3}.json`
(`sentinel.json` was NOT created — the sentinel never ran).
The feeder was never invoked; no service was started,
stopped, or modified; nothing was installed.
