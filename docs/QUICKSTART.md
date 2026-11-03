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
```

The tools themselves need **Python 3.11+ and git, nothing
else** — the kernel is standard-library only, and every
`tools/jq*.py` command runs on a bare interpreter. The test
suite additionally needs `pytest`:

```
python3 -m pytest -q        # install check, if pytest is present
```

The suite is green on the reference platforms (Linux x86_64
and WSL2). One executor test depends on bubblewrap holding
on your kernel: on Jetson/tegra kernels it does not, and
that single test fails there — a property of the device,
recorded in `docs/DEVICES.md`, not a broken install. (Node
is needed only for the optional TypeScript conformance
suite; Rust only for that port.)

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

**Workspace** means the directory the agent runs in (its
cwd). Its log lives at `<workspace>/.jacquard/kernel.jsonl`.
The fleet pattern is a dedicated work directory beside the
clone, so the governed record and the code stay separate.

1. Install the adapter — follow `adapters/zcode/README.md`
   (the plugin surface; on current ZCode builds the plugin
   is the route that runs). Know the scope before you run
   it: the plugin install is **machine-global, not
   per-workspace** — it creates a marketplace directory
   under your home and enables the plugin in
   `~/.zcode/cli/setting.json`, so it affects every zcode
   session on the box. The install script's optional
   marketplace-dir argument keeps the marketplace inside a
   directory of your choosing. Verified builds:
   zcode-app-cli 3.16.2-38 (Jetson Orin) and 3.16.3-40
   (ProArt WSL2). A `Duplicate plugin hooks file ignored`
   warning during install is known and harmless — the
   plugin still enables and its hooks fire.
2. Start your agent in the workspace, with
   `JACQUARD_LOG=<workspace>/.jacquard/kernel.jsonl` and
   `JACQUARD_PRODUCER=<a name for this seat>` in its
   environment. Headless works — the fleet runs it this
   way — with one recipe that matters: **put the retry
   rule in the agent's prompt.** A queued action is not a
   rejection; the agent must retry the identical action
   until it is allowed, and say so in its tasking, e.g.
   *"If an action is QUEUED, wait briefly and retry the
   exact same action — an operator is deciding it in a
   batch. Never work around a queued action."*
3. Operate the queue while the agent works:
   `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl queue`,
   then `decide approve|deny <id> --hash <binding>` per
   item. **Decide promptly**: a headless seat retries
   within seconds, so work in short polling passes (every
   few seconds) rather than one late batch — an approval
   only takes effect when the seat retries after it. The
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
agent on the box). Work against a **copy** of the governed
log — the log plus its sibling journal
(`<log>.gpu-journal.jsonl`; jqgpu expects both side by
side). Copy them from wherever the deployment keeps them,
and sha256 the log before and after you copy it back, so
the record you return is the record you took.

```
python3 tools/jqgpu.py --log <gpu-log> counts
#    submitted / allowed / held / denied / dispatched /
#    completed / failed, re-derived from the log
python3 tools/jqgpu.py --log <gpu-log> submit \
    --producer <you> --name <job-name> --cmd <command> \
    --output gpu-artifact:<job-name>
#    a new job proposal: the kernel decides it; an allowed
#    job is then dispatched with `jqgpu dispatch` and its
#    outcome journalled by `jqgpu poll`
```

A literal bench job, the fleet's standard shape:

```
python3 tools/jqgpu.py --log <gpu-log> submit \
  --producer jacquard-build --name bench-1 \
  --cmd 'mkdir -p ~/jacquard-gpu-live && ~/ml/.venv/bin/python -c "import torch,json; x=torch.randn(1024,1024,device='"'"'cuda'"'"'); y=x@x; torch.cuda.synchronize(); json.dump({'"'"'job'"'"':'"'"'bench-1'"'"','"'"'sum'"'"':float(y.sum())}, open('"'"'/home/caseydigennaro/jacquard-gpu-live/bench-1.json'"'"','"'"'w'"'"'))"' \
  --output gpu-artifact:bench-1
```

Note the two halves of `--output` vs `--cmd`: the output is
an **artifact id** (`gpu-artifact:<name>`); the actual file
path lives inside the command, on the GPU box.

**The successor rule** (the queue's own law, and the one
thing that strands newcomers): a finite job in gpuq runs
only when another job is queued **behind** it. The fleet
keeps a declared sentinel job standing last in the queue
for exactly this reason. When you dispatch a job, dispatch
a sentinel behind it (the slice-22/25 reports show the
shape), or your job waits — `jqgpu poll` will simply keep
reporting it queued, and the queue's own status file shows
the `no_successor_holds` reason. Re-running `dispatch` is
safe: it re-lists already-dispatched jobs as it reconciles
(`adopted` tells you whether it took over an existing gpuq
job), and outcomes are established by `poll` + the journal,
not by the dispatch listing.

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

The board is a **git clone** (the fleet's is
`agent-inbox`) containing a `schedule/` directory of
per-box files, and applied bookings are **git commits
pushed to its origin**. `--inbox` must therefore be a real
clone with an `origin` remote — jqbook checks this up
front and refuses a plain copy before anything is decided.
The check proves an origin exists, not that pushing to it
is safe: **never propose against a copy whose origin is
the live board** (a copied `.git` keeps the live origin,
and a successful propose would push your booking onto it).
For a scratch or test board, give the copy its own remote:

```
git clone <board> scratch-board
git clone --bare <board> scratch-board-origin.git
git -C scratch-board remote set-url origin <abs path>/scratch-board-origin.git
#    every push now lands in the scratch remote, never the live board
```

```
# one-time: import the board's live rows as facts
#    (a fresh log only — init refuses a non-empty log;
#     `imported` counts rows still live at their check-by,
#     `skipped` the dead ones; --boxes <a,b> limits the import)
python3 tools/jqbook.py --log <log> --inbox <board-clone> init
# each booking is then a proposal the kernel decides first
python3 tools/jqbook.py --log <log> --inbox <board-clone> propose \
    --lane <your-lane> --box orin --seat zcode \
    --from "2026-11-03 19:45" --planned 2h \
    --what "what the time is for"
python3 tools/jqbook.py --log <log> queue          # held items
python3 tools/jqbook.py --log <log> --inbox <board-clone> release --id <booking-id>
python3 tools/jqbook.py --log <log> --inbox <board-clone> complete --id <booking-id>
python3 tools/jqbook.py --log <log> counts
```

All times are **UTC** ("YYYY-MM-DD HH:MM"). `propose`
prints the decision as JSON: a booking that proceeds shows
`machine_state: "active"` with `committed: true` and a
`board_commit`; the `booking_id` in that output is the id
every later verb takes. Authority, in one breath: `--lane`
names who is booking (your own lane by default); a lane's
**effective rank** is the lower of the rank it asserts
(`--rank`, default 10) and the **ceiling** it has been
granted (`--grant` records a grant for the proposing
lane). A lane with no grant books at
effective rank 0 — fine for an uncontended seat, and it
loses any contest. Against a live booking of higher
effective rank you are preempted or held; at **equal**
rank the challenger **holds** for an operator (the interim
tie disposition) — `queue` shows it, `release --id` is the
operator letting it proceed anyway, `complete --id` closes
a booking whose work is done (marking its board row DONE
— itself a commit pushed to the board — if this
deployment applied it, or recording the close kernel-side
only for a row another lane owns).

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
