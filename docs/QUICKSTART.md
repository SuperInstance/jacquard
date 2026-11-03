# Quickstart

Jacquard governs what software agents may do: every action an
agent wants to take becomes a **proposal**, a small kernel
decides it against versioned policy, human approvals batch
into a **queue** instead of interrupting, and every decision
lands in an append-only **record** you can replay. This page
takes you from a clone to your first governed action, then to
the profile that matches your machine.

**Install state, plainly:** Jacquard is not on PyPI / npm /
crates.io yet (first publication is a pending owner step —
see `docs/PUBLISHING.md`). Until then, install from git:

```
git clone https://github.com/SuperInstance/jacquard
cd jacquard
python3 -m pytest -q        # the suite is green; this is
                            # also your install check
```

You need Python 3.11+ and git. Nothing else: the kernel is
standard-library only. (Node is needed only for the optional
TypeScript conformance suite; Rust only for that port.)

## Your first governed action (about a minute)

The decision queue is the operator's surface. This drill
runs it end to end — proposals in, queue presented,
hash-bound batch decisions, an action executed, and a
replay of the whole story:

```
# 1. Seed a demo log (two queued proposals, one dispatch).
#    The log must be FRESH — seed-demo refuses a non-empty log.
rm -f /tmp/kernel.jsonl
python3 tools/jq.py --log /tmp/kernel.jsonl seed-demo
#    prints JSON: {"queued": {<id>: <binding>, ...},
#                  "dispatched": <id>, "action": <id>/action-0}

# 2. Present the queue (note each item's binding hash)
python3 tools/jq.py --log /tmp/kernel.jsonl queue

# 3. Decide, hash-bound: approve one item, deny the other
#    (either assignment works; canonical: approve alice's
#    notify, deny bob's spend). A wrong --hash fails with
#    "binding mismatch" and changes nothing — you can only
#    approve the item you were shown.
python3 tools/jq.py --log /tmp/kernel.jsonl decide approve <id> --hash <binding>
python3 tools/jq.py --log /tmp/kernel.jsonl decide deny <id> --hash <binding>

# 4. Execute the dispatched action through the sandboxed executor
python3 tools/jq.py --log /tmp/kernel.jsonl execute
#    prints: executed <id>/action-0: exit 0 via subprocess -> state confirmed

# 5. Replay each proposal end to end
python3 tools/jq.py --log /tmp/kernel.jsonl replay <approved-id>
python3 tools/jq.py --log /tmp/kernel.jsonl replay <denied-id>
python3 tools/jq.py --log /tmp/kernel.jsonl replay <dispatched-id>
#    the approved item ends "final proposal state: closed";
#    the denied one "refused"; the dispatched one "closed",
#    its transitions including the executor's confirm
```

You have now met the four ideas in the order a user meets
them: a **proposal** (an agent asks), a **decision** (policy
allows, denies, or queues it), the **queue** (you decide a
batch, hash-bound, in one pass), and the **record** (the log
replays every step). Everything else in Jacquard is one of
these four, at larger scale.

## Pick your profile

### A coding-agent seat (workstation or front-room box)

If you run a coding agent (the fleet uses ZCode), the
adapter puts its tool calls under kernel decision: reads
run at once; writes, shell commands and network actions
queue for your batched decision; an approval authorises
exactly one execution of exactly the action you saw.

1. Install the adapter for your workspace — follow
   `adapters/zcode/README.md` (the plugin surface; on
   current ZCode builds the plugin is the route that runs).
2. Start your agent in the workspace. Its log lives at
   `<workspace>/.jacquard/kernel.jsonl`.
3. When the agent pauses on a queued action, decide the
   batch from the repo:
   `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl queue`
   then `decide approve|deny <id> --hash <binding>` per
   item. The agent retries the identical action; the
   approval is consumed once, and the outcome is recorded.

Per-device notes for this profile (WSL workstation, Jetson
front room) are in `docs/DEVICES.md`.

### A shared job queue (GPU box)

If several producers share one expensive queue, govern the
submissions: a job reaches the queue only if the kernel
allowed it, holds wait for a batched operator decision, and
outcomes journal back into the same log.

The fleet's instance is the Thor's gpu-queue, driven by
`tools/jqgpu.py` over a per-dispatch bridge (no resident
agent on the box). Against the existing governed log:

```
python3 tools/jqgpu.py --log <gpu-log> counts
#    submitted / allowed / held / denied / dispatched /
#    completed / failed, re-derived from the log
python3 tools/jqgpu.py --log <gpu-log> submit \
    --producer <you> --name <job-name> --cmd <command> \
    --output <artifact-path>
#    a new job proposal: the kernel decides it; an allowed
#    job is then dispatched with `jqgpu dispatch` and its
#    outcome journalled by `jqgpu poll`
```

To run your own: `jqgpu init` a log for your queue, state
the governed job class in its policy record before the
first dispatch, and submit through the bridge — never
around it. The full live record of the fleet's deployment
is `docs/slice22-live-report.md` and
`docs/slice25-live-report.md`.

### A shared schedule (server / coordination point)

If several agents book shared machines, govern the
bookings: contention and authority are kernel senses, ties
hold for an operator instead of silently winning, and the
schedule itself stays a plain git-backed board.

```
# one-time: import the board's live rows as facts
python3 tools/jqbook.py --log <log> --inbox <board-clone> init
# each booking is then a proposal the kernel decides first
python3 tools/jqbook.py --log <log> --inbox <board-clone> propose \
    --box orin --seat zcode --from "2026-11-03 19:45" \
    --planned 2h --what "what the time is for"
python3 tools/jqbook.py --log <log> queue     # held items
python3 tools/jqbook.py --log <log> --inbox <board-clone> release --id <booking>
```

The deployment record is `docs/slice30-device-matrix.md`.

### A single-user laptop

One human, one machine, local automation: the same kernel
and operator CLI, no server, no queue-sharing — your
scripts and agents propose, you decide in batches, the log
on the laptop is the record. The drill above is the whole
install; keep the log under your home directory (every
tool takes `--log`) and let your automations submit
through `tools/jq.py` / the service on loopback
(`tools/jqserve.py`, see the README's service section).
Fleet status: this profile is prepared but not yet
deployed on the fleet's laptop — see `docs/DEVICES.md`
for the honest state of that cell.

## Where to go next

- `docs/ONBOARDING.md` — the concepts in meeting order,
  each introduced by the example that needs it.
- `starters/` — one kit per proven use, each ending with
  you governing your own real task.
- `docs/DEVICES.md` — what differs per device, from the
  deployments' evidence.
- `spec/SPEC.md` — the contract, when you want the whole
  truth; `docs/BUILDERS-LOG.md` — how it got this way.
