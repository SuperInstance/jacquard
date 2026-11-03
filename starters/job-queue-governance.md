# Starter kit: job-queue governance

**Use:** several producers share one expensive queue
(GPU time, a printer farm, a rate-limited API). A job
reaches the queue only if the kernel allowed it; an
unknown producer's job holds for a batched operator
decision; outcomes journal back into the same log.

**Proven by:** the Thor's gpu-queue, in production on the
fleet's GPU server. At the last full audit its log counted
17 submitted / 10 allowed / 2 held / 5 denied / 12
dispatched / 10 completed / 1 failed; a later
independently-operated session took it to 19 submitted
and 12 completed. The deployment record is
`docs/slice30-device-matrix.md`.

## 1. Copy the log, both halves

Never govern against the canonical log in place: work
against a copy, then return it. The log has a sibling
journal (`<log>.gpu-journal.jsonl`) — copy both, and
sha256 the log on both sides of the round trip:

```
cp <deployment>/kernel.jsonl work/kernel.jsonl
cp <deployment>/kernel.jsonl.gpu-journal.jsonl work/kernel.jsonl.gpu-journal.jsonl
python3 tools/jqgpu.py --log work/kernel.jsonl counts
```

## 2. Submit through the kernel

```
python3 tools/jqgpu.py --log work/kernel.jsonl submit \
  --producer <you> --name <job-name> --cmd <command> \
  --output gpu-artifact:<job-name>
```

`--output` is an artifact **id**; the file path lives
inside `--cmd`, on the queue box. A producer the policy
record doesn't know is **held**, not denied: the kernel
records the hold and the job waits for you.

## 3. Decide the hold

```
python3 tools/jq.py --log work/kernel.jsonl queue
python3 tools/jq.py --log work/kernel.jsonl decide approve <id> --hash <binding>
```

One approval authorises one dispatch. Then:

```
python3 tools/jqgpu.py --log work/kernel.jsonl dispatch
python3 tools/jqgpu.py --log work/kernel.jsonl poll   # until completed/failed
```

## 4. Keep a sentinel standing last

**The queue's law: a finite job runs only with another
job queued behind it.** Submit a declared sentinel behind
your job (the deployment's own shape — producer
`jacquard-build`, a no-op name like `jacquard-sentinel-N`)
before expecting completion, or your job sits queued with
`no_successor_holds` in the queue's status. The sentinel
is the next window's standing successor; the end state of
every window is a sentinel standing last.

## 5. Return the record

Copy the updated log + journal back to the deployment and
verify sha256 equality both sides. `counts` after should
show your job completed and the sentinel standing.

## Limits, honestly

- The gate prices a declared successor as ordinary
  production until a real successor marker exists (a named
  residual, recorded in
  `docs/slice27-consumption-policy-v2.md`).
- The consumption gate (`--consumption-gate`) is built
  and tested but activates only for a job class running
  ≥ ~5 GPU-minutes; below that, governance is the allow /
  hold / deny decision, not pricing.
