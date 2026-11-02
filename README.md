# Jacquard

A supervised runtime where untrusted producers submit proposals, a small auditable kernel decides what may change shared state or act on the world, learned behaviours are deployed under test, and every decision can be replayed from an append-only log.

## What this is

Producers (people, language models, programs, sensors) differ enormously in cost, latency, reliability and authority, but they all emit the same kind of thing: proposals. Jacquard separates proposing from deciding:

- **Proposals** arrive in a sealed envelope format and are never trusted. Each proposal declares its effects (what it would write, send, spend, or irreversibly do).
- **Tentative state** holds undecided work as candidate sets, so nothing becomes shared truth just by being suggested.
- **The kernel** — a sequencer, an append-only hash-chained log, and a versioned policy gate — is the only part that can change committed state. It answers every submission with a verdict: accepted, decided, or refused with a named reason.
- **Approvals are batched.** Proposals that need a human decision go to a decision queue; everything else keeps moving. Asking never stalls the system.
- **Behaviour is extended by definition.** New behaviour enters as dictionary definitions composed from a fixed set of 26 primitives. A definition's effects are computed from its parts, not declared, so a definition cannot hide what it does. Learned behaviours (standing rules) are deployed through evaluation, shadow running, and staged activation, and can be revoked.
- **Everything replays.** Committed state is a fold of the log; any decision can be re-derived and checked.

## Repository layout

- `spec/` — the specification (SPEC.md, currently version 0.3) and golden vectors. The spec is the contract; implementations in any language must match the vectors byte-for-byte.
- `src/jacquard/` — the Python reference implementation of the kernel, including the machine profile (`machines.py`), the seven lifecycle machine definitions (`lifecycles.py`), the WFQ scheduler (`scheduler.py`), senses (`senses.py`), the decision-model provider seam (`providers.py`), the learner (`learner.py`), state export bundles (`bundle.py`), and the booking application profile (`booking.py`). Beside the kernel sit the shared operator presentation (`present.py` — the queue/replay/status rendering both the CLI and the service use) and the network service (`service.py`, Phase 5 slice 13).
- `adapters/` — adapters that live outside the kernel: decision-model providers (the kernel imports no provider-specific code) and the sandboxed executor.
- `tools/` — operator and build tools: the operator CLI (`jq.py`), the service runner (`jqserve.py`), the golden-vector generator, the shadow-trial runner.
- `tests/` — unit tests plus the acceptance suite (a replay of a real GPU job-queue record through the kernel).
- `conformance/` — the second-language conformance suite: an independent TypeScript implementation written from the spec alone, its gap report, and the fixtures it folds (see `conformance/README.md`).
- `docs/BUILDERS-LOG.md` — how this was built: decisions, reasons, dead ends, in the order they happened.
- `docs/PROGRAMME.md` — the programme record: what Jacquard is, how it got here, the rulings, and the verified build state (mirrored verbatim from the programme workspace, which remains its working home).
- `docs/USE-CASE-VOID-SCAN.md` — the market survey behind the build order: 25 products graded against six capability voids no incumbent holds together (mirrored verbatim from the programme workspace).

## Status

Phase 1 (complete): reference kernel (log, sequencer, dictionary with computed effects, policy gate with batched decision queue) plus the replay acceptance suite.

Phase 2 (complete): lifecycle machines and the machine-profile checker have landed (spec section 10) — the seven lifecycle machines are definitions in the repo, statically checked with named refusals, and the kernel runs its proposal, action and approval lifecycles through them. Queued proposals can now also be rejected or expired, not only released. Fair-queue scheduling, budgets and prices, and the senses framework have also landed (spec section 11): one WFQ scheduler arbitrates sequencer admission, executor slots and decision-queue attention; budgets are accounted from the log to the unit; senses publish named readings with their methods stated. Decision models plug in behind a provider interface as advisors only (spec section 13; `adapters/typesafe_jev.py` is the first adapter, outside the kernel). The learner has also landed (spec section 12): repeated decision shapes are mined into candidate standing rules, evaluated offline, shadow-run, promoted through canary to active on scored evidence, auto-demoted on regression, and revocable in one call — every stage a machine transition in the log. State export bundles have also landed (spec section 14): configuration and definitions travel between kernels, standing rules travel unproven and re-enter at shadow, and authority, credentials and budgets never travel — smuggling any of them is refused by name.

Phase 3 (complete): second-language conformance has landed — a TypeScript implementation written from the spec alone reproduces the golden vectors and folds the 3,295-entry real replay log to the identical state hash (conformance/).

Phase 3 (continued): a sandboxed executor adapter has landed (`adapters/executor.py`, spec section 10.5) together with a live shadow trial on the fleet's real booking board — 88% agreement with the incumbent process, every disagreement classified (docs/shadow-trial-2026-11-02.md). The operator CLI has also landed (`tools/jq.py`): the decision queue as a command-line surface with hash-bound batch approvals, executor driving, and per-proposal replay — see the quickstart below; a cold agent reproduced the drill from this README alone.

Phase 4 (complete): the completeness probes closed the shadow trial's three expressiveness findings (docs/completeness-probes-2026-11-02.md) with no new primitives and no new fold section. Interval contention is a kernel sense consumed by machine guards (spec section 11.3); conditional starts are a `wait` field on the proposal body, re-evaluated by a sequencer pump under pinned ordering rules (spec section 7.1); authority priority is rank as data, an authority sense that recognises only operator grants, and preemption as ordinary operator proposals, in a booking application profile shipped as definitions (spec section 11.4). The operator CLI annotates waiting items and authority ties in the queue listing.

Phase 5 (in progress): beachhead 1 — the supervision layer for coding-agent fleets. Slices 13 and 14 have landed: the network service (`src/jacquard/service.py`, run via `tools/jqserve.py`) exposes the operator CLI's verbs over HTTP — see the service section below — and batched queue notifications (`tools/jqnotify.py`) — see the notifications section below. Slices 12 (a live adapter to a real coding agent) and 15 (the measured proof run) are the rest of the phase.

Not built yet: packaging beyond this release (the repo is the distribution). See the builder's log for the current state and honest per-slice verdicts.

## Running the tests

```
python3 -m pytest -q
```

## Quickstart: the operator drill

The decision queue is the operator's surface. This drill runs it
end to end — proposals in, queue presented, hash-bound batch
decisions, actions executed, replay — in about a minute. From
the repo root:

```
# 1. Seed a demo kernel log (two queued proposals, one dispatch).
#    The log must be FRESH — seed-demo refuses a non-empty log.
rm -f /tmp/kernel.jsonl
python3 tools/jq.py --log /tmp/kernel.jsonl seed-demo
#    prints JSON: {"queued": {<id>: <binding>, ...},
#                  "dispatched": <id>, "action": <id>/action-0}

# 2. Present the queue (note each item's binding hash)
python3 tools/jq.py --log /tmp/kernel.jsonl queue

# 3. Decide, hash-bound: approve one item, deny the other
#    (either assignment works; canonical: approve alice's notify,
#    deny bob's spend). A wrong --hash fails with "binding
#    mismatch" and changes nothing — you can only approve the
#    item you were shown.
python3 tools/jq.py --log /tmp/kernel.jsonl decide approve <id> --hash <binding>
python3 tools/jq.py --log /tmp/kernel.jsonl decide deny <id> --hash <binding>
#    (or batch: lines of "<id> <binding>" in a file, decided with
#     the command's action — decide approve --batch decisions.txt —
#     or mixed lines of "<approve|deny> <id> <binding>")

# 4. Execute the dispatched action through the sandboxed executor
python3 tools/jq.py --log /tmp/kernel.jsonl execute
#    prints: executed <action id>: exit 0 via <sandbox>
#            -> state confirmed

# 5. Replay proposals end to end — once per id
python3 tools/jq.py --log /tmp/kernel.jsonl replay <approved-id>
python3 tools/jq.py --log /tmp/kernel.jsonl replay <denied-id>
python3 tools/jq.py --log /tmp/kernel.jsonl replay <dispatched-id>
#    the approved item ends with "final proposal state: closed";
#    the denied one with "refused"; the dispatched one "closed",
#    its transitions including the executor's confirm
```

Success looks like: step 3 prints `approved <id>` / `denied
<id>` and a following `queue` reports the queue empty; step 4
reports the action confirmed; step 5's replay shows the queued
decision, the operator's decision, and the execution, in log
order.

## The network service

The kernel is also reachable over HTTP, so a second machine can
operate it: the same verbs as the operator CLI, against the same
log, with the hash-binding rules unchanged. The service is
standard-library only (the repo stays zero-dependency).

Run it (from the repo root, on the machine that owns the log):

```
python3 tools/jqserve.py --log /tmp/kernel.jsonl
# binds 127.0.0.1:8730 by default; --host / --port to change
```

Endpoints (JSON in, JSON out; every response that renders
operator text carries it in a `text` field):

| Route | Verb |
|---|---|
| `POST /seed-demo` | seed a fresh log with the demo proposals (refuses a non-empty log, like the CLI) |
| `POST /proposals` | submit one envelope (the envelope object itself, or `{"envelope": ...}`); returns the kernel's verdict |
| `GET /senses` | all published sense readings in the log |
| `GET /senses/<name>` | one published reading by name (404 if none was published) |
| `GET /queue` | the decision queue: structured `items` plus `text` |
| `POST /decide` | decide: `{"action", "proposal_id", "hash"}`, or `{"decisions": [...]}` / `{"action", "batch": [...]}` for a batch |
| `GET /replay/<proposal_id>` | the proposal's replay |
| `GET /status` | kernel status |

Queue presentation and replay are byte-for-byte identical to
the CLI's output for the same log: both surfaces render through
`src/jacquard/present.py`, and `tests/test_service.py` runs the
slice-10 operator drill through HTTP and the CLI on identical
logs and diffs every rendering (and the resulting log files).

Decisions stay hash-bound over the wire: a `hash` that does not
match the binding the queue presented fails with 409, prints
the CLI's binding-mismatch line, and changes nothing.
Successful batch items in a mixed batch still apply, exactly
as the CLI processes the rest of a batch.

Senses are the owning kernel's *published* readings — values
the kernel computed and wrote into its log, with their methods
and `as_of_seq`. The service serves those publications; it
never recomputes a reading (contention, authority, or any
other) from the record on a consumer's behalf.

### Auth story, honestly

- **Loopback (the default).** Binding 127.0.0.1 trusts every
  local user of the host: anyone who can open a local TCP
  connection can operate the kernel. No token is required,
  because on loopback a token would only pretend to separate
  users the OS already shares the port with.
- **Non-loopback (LAN).** Requires BOTH the explicit
  `--allow-remote` flag AND a bearer token in the
  `JACQUARD_SERVICE_TOKEN` environment variable; without the
  token the service refuses to start on a non-loopback bind.
  When a token is configured it is checked on every request
  (`Authorization: Bearer <token>`); a missing or wrong token
  gets 401 and changes nothing.
- **What the token does:** keeps unauthorised machines on the
  LAN from operating the kernel, and nothing more. It is one
  shared secret — not per-user identity, not an audit of *who*
  decided (decisions are recorded as `operator`, as with the
  CLI).
- **What it does not do:** there is **no TLS**. The token and
  every payload cross the network in clear text, so anyone who
  can observe LAN traffic can read proposals and replay the
  token. Run it only on a LAN you trust, or inside a tunnel
  (SSH, WireGuard, Tailscale) — the token is a door lock, not
  an armoured car.

## Queue notifications (Phase 5, slice 14 — built)
`tools/jqnotify.py` is the decision queue's tap on the shoulder:
it folds the log, computes the current queue snapshot, and fires
ONE batched summary when the queue waits at or beyond a
configurable age or count. The summary carries counts by effect
class, the oldest item's age, the total queue depth, and the
queue snapshot hash — never a per-item listing by default
(`--verbose` lists ids on the console only). It proposes nothing
and approves nothing; decisions stay in the CLI/service.
python3 tools/jqnotify.py --log kernel.jsonl [--max-age-s N] [--max-count N] [--deliver]
- **Age is log time.** The kernel log has no wall-clock
  timestamps; its clock is the log itself (spec section 5,
  primitives P2/P6). An item's age is the distance in log
  entries between the decision entry that queued it and the
  newest substantive entry (the notifier's own records do not
  age the queue). `--max-age-s` (alias `--max-age`) is therefore
  in log entries. Every summary states its age mode
  (`log-entries`) and is recomputable from the log alone.
- **Thresholds** trip at or beyond the limit: oldest age
  `--max-age-s` (env `JQNOTIFY_MAX_AGE_S`, default 100 entries),
  depth `--max-count` (env `JQNOTIFY_MAX_COUNT`, default 5).
  `--check` reports whether a notification would fire without
  firing it.
- **Repeat suppression.** A state file (default
  `<log>.jqnotify-state.json`) records the last notified
  snapshot; a run re-fires only on a material change (new /
  changed queue contents, or the same oldest item strictly
  older on substantive log growth) — never on a poll loop over
  an unchanged queue.
- **Where firings land.** (a) A `queue-notification`
  checkpoint record appended to the kernel log itself,
  carrying the snapshot hash and the exact summary numbers —
  fold-transparent (the state hash is unchanged by it), and
  verifiable after the fact with
  `python3 tools/jqnotify.py --log kernel.jsonl --verify`,
  which re-folds the prefix before each record and recomputes
  its summary. (b) With `--deliver`, a Markdown drop committed
  to the fleet's agent-inbox repo under `verdicts/`, numbered
  sequentially in that folder's verdict format. Without
  `--deliver`, nothing leaves the machine.
