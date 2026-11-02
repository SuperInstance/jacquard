# Provenance: gpu-queue dataset

Copied read-only from the Thor on 2026-11-02 (`~/gpu-queue/`),
the live record of the gpu-queue keeper that ran the Foundry
feeder and finite jobs on that machine.

Files:

- `events.jsonl` — 3,274 events: 1,637 `dispatch` and 1,637
  `finish`, strictly alternating, every finish exit 0, every
  dispatch attempt 1. md5 `f9a10545d47d4e16c6b993a3e9c6a3d5`.
- `queue.json` — 1,637 jobs in order: 2 finite (`job-1`,
  `job-2`), then 1,635 feeder jobs (`feeder-1` … `feeder-1635`).
  Dispatch order in `events.jsonl` is identical to this order.
- `idle.jsonl` — 1,137 idle intervals, all after the run ended,
  all closed by foreign work on the GPU.
- `status.json` — snapshot from 2026-11-02, after the run:
  feeder disabled, `jobs_done 1637`, `jobs_failed 0`,
  `no_successor_holds {}`, `halted null`.
- `daemon.py`, `gpuq`, `README.md` — the daemon whose behaviour
  the record embodies; the dictionary definitions in
  `tests/acceptance/queue_dictionary.py` are derived from it.

Recorded window: 2026-10-27 23:22:36 -0800 to
2026-10-28 18:41:26 -0800.

What the record does NOT contain: any hold, any start failure,
any halt. The daemon's hold and halt rules are therefore covered
by reconstructed fixtures in `tests/data/synthetic/`, derived
from `daemon.py` and marked as reconstructions there.

Reconstructions used by the replay (disclosed, not hidden):

- The feeder was enabled throughout the run. `status.json` shows
  it disabled days later; but the run materialised and dispatched
  1,635 feeder jobs under a rule that only dispatches the head
  job when a successor exists or the feeder is enabled, and the
  daemon state ended at feeder index 1635 — so it was enabled.
- At every recorded dispatch the foreign-work sense was false:
  a dispatch happened, and the daemon never dispatches on a tick
  where foreign work holds the GPU.

No credentials appear in this dataset; job commands reference
local paths only.
