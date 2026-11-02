# Thor GPU successor queue

The standing machinery behind Casey's rule: **no finite GPU job is
dispatched without a named successor behind it, and idle GPU time is a
logged deficit, not a discovery made later.**

Built 2026-10-27 after the overnight audit of Oct 25–26 found ~28.9
GPU-hours idle because every lane was a finite job with nothing queued
behind it, and after the casting-call bench queue was found exhausted
again on the morning of Oct 27 (GPU at 0% while resident models sat
loaded). Earlier attempts put an *agent* in charge of the queue
(queue owners #1–#5); agents end, so the queues died with them. This
queue is a small service instead — it survives sessions, reboots and
agent turnover. Process documented here as it was built: preflight
found the GPU at 0% with five resident servers holding ~52 GB and no
work running — the deficit live at the moment of construction.

## How it works

- `daemon.py` (systemd user service `gpu-queue`, linger is on) polls
  every 20 s: GPU utilisation, the running job, the queue.
- **Successor rule, enforced at dispatch:** a finite job starts only
  when another job is queued behind it or the feeder is on. A job with
  no successor *holds*; the hold is recorded against its lane in
  `queue.json` (`meta.no_successor_holds`) and surfaces in the deficit
  report.
- **The feeder** is the standing successor of last resort: the
  foundry-loop's own variant-generation job (mint a family of 8,
  rotating fishing_boat → harbor_house → pier → spruce, seeds advancing
  by 1000 each round), materialised one instance at a time. Turn it off
  and the queue runs dry honestly — jobs hold and idle accrues, both
  logged, instead of the GPU quietly doing nothing.
- **Start failures:** a job that dies within 25 s with a nonzero exit
  is retried once. A second failure halts dispatching entirely: GPU
  left idle, the job's log preserved under `job-logs/`, the halt
  recorded in `queue.json` (`meta.halted`) and in `events.jsonl`.
  A job that runs past the grace window and then fails is its lane's
  failure, recorded, and the queue moves on to the successor.
- **Idle accounting:** whenever no queue job is running and GPU
  utilisation is ≤15%, an idle interval is open. It closes — with
  start, end and duration written to `idle.jsonl` — when a job starts
  or when foreign work takes the GPU (utilisation >15% that isn't
  ours; the GPU was busy, and the interval says so).
- **Restarts:** the unit uses `KillMode=process`, so a daemon restart
  never kills a running job; the daemon reattaches to it by pid.

## For lanes: adding work

```
~/gpu-queue/gpuq add --lane casting-call \
  --name "Bench battery B on resident model X" \
  --cmd "cd /home/caseydigennaro/... && ./run-battery.sh B"
~/gpu-queue/gpuq status     # what's running, what's next, idle total
~/gpu-queue/gpuq list       # every job and its state
~/gpu-queue/gpuq feeder off # stop the standing feeder (queue can run dry)
```

Add your successor when you add your job. Only work already named by
an existing lane belongs here — the queue starts nothing paid and
downloads nothing.

## Files

- `queue.json` — the queue itself, rules stated at the top of the file
- `status.json` — live picture, rewritten every poll
- `idle.jsonl` — closed idle intervals (start, end, duration, why closed)
- `events.jsonl` — dispatch / finish / hold / halt / failure record
- `job-logs/` — one log per run, kept on failure
