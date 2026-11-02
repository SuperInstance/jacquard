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

- `spec/` — the specification (SPEC.md, currently version 0.2) and golden vectors. The spec is the contract; implementations in any language must match the vectors byte-for-byte.
- `src/jacquard/` — the Python reference implementation of the kernel, including the machine profile (`machines.py`), the seven lifecycle machine definitions (`lifecycles.py`), the WFQ scheduler (`scheduler.py`), senses (`senses.py`), the decision-model provider seam (`providers.py`), the learner (`learner.py`), and state export bundles (`bundle.py`).
- `adapters/` — adapters that live outside the kernel: decision-model providers (the kernel imports no provider-specific code) and the sandboxed executor.
- `tools/` — operator and build tools: the operator CLI (`jq.py`), the golden-vector generator, the shadow-trial runner.
- `tests/` — unit tests plus the acceptance suite (a replay of a real GPU job-queue record through the kernel).
- `conformance/` — the second-language conformance suite: an independent TypeScript implementation written from the spec alone, its gap report, and the fixtures it folds (see `conformance/README.md`).
- `docs/BUILDERS-LOG.md` — how this was built: decisions, reasons, dead ends, in the order they happened.

## Status

Phase 1 (complete): reference kernel (log, sequencer, dictionary with computed effects, policy gate with batched decision queue) plus the replay acceptance suite.

Phase 2 (complete): lifecycle machines and the machine-profile checker have landed (spec section 10) — the seven lifecycle machines are definitions in the repo, statically checked with named refusals, and the kernel runs its proposal, action and approval lifecycles through them. Queued proposals can now also be rejected or expired, not only released. Fair-queue scheduling, budgets and prices, and the senses framework have also landed (spec section 11): one WFQ scheduler arbitrates sequencer admission, executor slots and decision-queue attention; budgets are accounted from the log to the unit; senses publish named readings with their methods stated. Decision models plug in behind a provider interface as advisors only (spec section 13; `adapters/typesafe_jev.py` is the first adapter, outside the kernel). The learner has also landed (spec section 12): repeated decision shapes are mined into candidate standing rules, evaluated offline, shadow-run, promoted through canary to active on scored evidence, auto-demoted on regression, and revocable in one call — every stage a machine transition in the log. State export bundles have also landed (spec section 14): configuration and definitions travel between kernels, standing rules travel unproven and re-enter at shadow, and authority, credentials and budgets never travel — smuggling any of them is refused by name.

Phase 3 (complete): second-language conformance has landed — a TypeScript implementation written from the spec alone reproduces the golden vectors and folds the 3,295-entry real replay log to the identical state hash (conformance/).

Phase 3 (continued): a sandboxed executor adapter has landed (`adapters/executor.py`, spec section 10.5) together with a live shadow trial on the fleet's real booking board — 88% agreement with the incumbent process, every disagreement classified (docs/shadow-trial-2026-11-02.md). The operator CLI has also landed (`tools/jq.py`): the decision queue as a command-line surface with hash-bound batch approvals, executor driving, and per-proposal replay — see the quickstart below; a cold agent reproduced the drill from this README alone.

Not built yet: any network service; packaging beyond this release (the repo is the distribution). See the builder's log for the current state and honest per-slice verdicts.

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
