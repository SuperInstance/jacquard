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
- `tests/` — unit tests plus the acceptance suite (a replay of a real GPU job-queue record through the kernel).
- `conformance/` — the second-language conformance suite: an independent TypeScript implementation written from the spec alone, its gap report, and the fixtures it folds (see `conformance/README.md`).
- `docs/BUILDERS-LOG.md` — how this was built: decisions, reasons, dead ends, in the order they happened.

## Status

Phase 1 (complete): reference kernel (log, sequencer, dictionary with computed effects, policy gate with batched decision queue) plus the replay acceptance suite.

Phase 2 (in progress): lifecycle machines and the machine-profile checker have landed (spec section 10) — the seven lifecycle machines are definitions in the repo, statically checked with named refusals, and the kernel runs its proposal, action and approval lifecycles through them. Queued proposals can now also be rejected or expired, not only released. Fair-queue scheduling, budgets and prices, and the senses framework have also landed (spec section 11): one WFQ scheduler arbitrates sequencer admission, executor slots and decision-queue attention; budgets are accounted from the log to the unit; senses publish named readings with their methods stated. Decision models plug in behind a provider interface as advisors only (spec section 13; `adapters/typesafe_jev.py` is the first adapter, outside the kernel). The learner has also landed (spec section 12): repeated decision shapes are mined into candidate standing rules, evaluated offline, shadow-run, promoted through canary to active on scored evidence, auto-demoted on regression, and revocable in one call — every stage a machine transition in the log. State export bundles have also landed (spec section 14): configuration and definitions travel between kernels, standing rules travel unproven and re-enter at shadow, and authority, credentials and budgets never travel — smuggling any of them is refused by name.

Phase 3 (in progress): second-language conformance has landed — a TypeScript implementation written from the spec alone reproduces the golden vectors and folds the 3,295-entry real replay log to the identical state hash (conformance/).

Phase 3 (continued): a sandboxed executor adapter has landed (`adapters/executor.py`, spec section 10.5) together with a live shadow trial on the fleet's real booking board — 88% agreement with the incumbent process, every disagreement classified (docs/shadow-trial-2026-11-02.md).

Not built yet: the operator CLI. See the builder's log for the current state and honest per-slice verdicts.

## Running the tests

```
python3 -m pytest tests/ -q
```
