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

- `spec/` — the specification (SPEC.md, currently version 0.6) and golden vectors. The spec is the contract; implementations in any language must match the vectors byte-for-byte.
- `src/jacquard/` — the Python reference implementation of the kernel, including the machine profile (`machines.py`), the seven lifecycle machine definitions (`lifecycles.py`), the WFQ scheduler (`scheduler.py`), senses (`senses.py`), the decision-model provider seam (`providers.py`), the learner (`learner.py`), state export bundles (`bundle.py`), and the booking application profile (`booking.py`). Also in the package, but outside the kernel, is the anchoring tooling (`anchor.py`, spec section 15) — the package's only non-standard-library dependency (`cryptography`, for Ed25519) is confined to it, and `import jacquard` never pulls it in — and the sealed-export tooling (`sealing.py`, spec section 16, stdlib only). Beside the kernel sit the shared operator presentation (`present.py` — the queue/replay/status rendering both the CLI and the service use) and the network service (`service.py`, Phase 5 slice 13).
- `adapters/` — adapters that live outside the kernel: decision-model providers (the kernel imports no provider-specific code), the sandboxed executor, and the ZCode coding-agent adapter (`zcode_hook.py` plus the installable surfaces in `zcode/`), which puts a real coding agent's tool calls under kernel decision (Phase 5 slice 12; the coding-agent profile itself is `src/jacquard/coding_agent.py`).
- `tools/` — operator and build tools: the operator CLI (`jq.py`), the service runner (`jqserve.py`), the anchoring CLI (`jqanchor.py`), the sealed-export CLI (`jqseal.py`), the golden-vector generator, the shadow-trial runner.
- `tests/` — unit tests plus the acceptance suite (a replay of a real GPU job-queue record through the kernel).
- `conformance/` — the second-language conformance suite: a TypeScript implementation in two parts — the original fold implementation written from the spec alone, and (slice 19) a full kernel port in `ts/kernel.ts` written from the Python reference — its gap report with the slice 19 closure notes, and the fixtures it folds (see `conformance/README.md`).
- `rust/` — the third implementation (Phase 8, slice 20): a Rust port of the kernel contract mirroring the TS layout, with its own conformance checker (the same 13 checks, zero SKIPs), a three-kernel cross-drill, and publish-shaped crate metadata under the qualified name `jacquard-kernel` (the crates.io name `jacquard` is taken; see `rust/README.md`).
- `docs/BUILDERS-LOG.md` — how this was built: decisions, reasons, dead ends, in the order they happened.
- `docs/PROGRAMME.md` — the programme record: what Jacquard is, how it got here, the rulings, and the verified build state (mirrored verbatim from the programme workspace, which remains its working home).
- `docs/USE-CASE-VOID-SCAN.md` — the market survey behind the build order: 25 products graded against six capability voids no incumbent holds together (mirrored verbatim from the programme workspace).

## Status

Phase 1 (complete): reference kernel (log, sequencer, dictionary with computed effects, policy gate with batched decision queue) plus the replay acceptance suite.

Phase 2 (complete): lifecycle machines and the machine-profile checker have landed (spec section 10) — the seven lifecycle machines are definitions in the repo, statically checked with named refusals, and the kernel runs its proposal, action and approval lifecycles through them. Queued proposals can now also be rejected or expired, not only released. Fair-queue scheduling, budgets and prices, and the senses framework have also landed (spec section 11): one WFQ scheduler arbitrates sequencer admission, executor slots and decision-queue attention; budgets are accounted from the log to the unit; senses publish named readings with their methods stated. Decision models plug in behind a provider interface as advisors only (spec section 13; `adapters/typesafe_jev.py` is the first adapter, outside the kernel). The learner has also landed (spec section 12): repeated decision shapes are mined into candidate standing rules, evaluated offline, shadow-run, promoted through canary to active on scored evidence, auto-demoted on regression, and revocable in one call — every stage a machine transition in the log. State export bundles have also landed (spec section 14): configuration and definitions travel between kernels, standing rules travel unproven and re-enter at shadow, and authority, credentials and budgets never travel — smuggling any of them is refused by name.

Phase 3 (complete): second-language conformance has landed — a TypeScript implementation written from the spec alone reproduces the golden vectors and folds the 3,295-entry real replay log to the identical state hash (conformance/).

Phase 3 (continued): a sandboxed executor adapter has landed (`adapters/executor.py`, spec section 10.5) together with a live shadow trial on the fleet's real booking board — 88% agreement with the incumbent process, every disagreement classified (docs/shadow-trial-2026-11-02.md). The operator CLI has also landed (`tools/jq.py`): the decision queue as a command-line surface with hash-bound batch approvals, executor driving, and per-proposal replay — see the quickstart below; a cold agent reproduced the drill from this README alone.

Phase 4 (complete): the completeness probes closed the shadow trial's three expressiveness findings (docs/completeness-probes-2026-11-02.md) with no new primitives and no new fold section. Interval contention is a kernel sense consumed by machine guards (spec section 11.3); conditional starts are a `wait` field on the proposal body, re-evaluated by a sequencer pump under pinned ordering rules (spec section 7.1); authority priority is rank as data, an authority sense that recognises only operator grants, and preemption as ordinary operator proposals, in a booking application profile shipped as definitions (spec section 11.4). The operator CLI annotates waiting items and authority ties in the queue listing.

Phase 5 (complete): beachhead 1 — the supervision layer for coding-agent fleets. All four slices landed: a live adapter to a real coding agent (ZCode — `adapters/zcode_hook.py`, `adapters/zcode/`; live-run record in `docs/slice12-live-run.md`), the network service (`src/jacquard/service.py`, run via `tools/jqserve.py`) — see the service section below — batched queue notifications (`tools/jqnotify.py`) — see the notifications section below — and the measured proof run (`docs/proof-run-2026-11-02.md`, raw inputs in `docs/proof-run/`): against the host's native permission flow, operator attention per 100 governed actions fell from ≈70 minutes (8 single-action interruptions) to ≈11 (3 batched passes), every decision landed in the replayable log, and the workload's one dangerous action was denied in batch review after the incumbent flow had waved it through. One named deficit carried forward — approvals did not yet compile into standing rules for queued shapes, because the learner trained on policy outcomes rather than operator decisions — and Phase 6 slice 16 closed it (below).

Phase 6 (complete): slice 16 — the operator-trained learner (spec section 12 as of 0.4). Queued shapes now carry a signature: a pure, log-derivable function of the proposal's requests that discriminates within the queued population (a shell command's skeleton with paths, urls and numbers abstracted; a write's file extension; a send's host), so the proof run's one regrettable shell shape splits into the distinct commands it actually covered. Operator release/reject decisions on queued items are first-class training labels, joined to the proposals they decided (the wait pump's mechanical re-decisions carry no operator field and never label). Mining runs two passes — the policy pass as before, and an operator pass whose candidates predict the operator's verdict — and operator-origin rules climb the same eval → shadow → canary → active ladder, scored on operator verdicts alone: rule-made decisions never grade themselves, and later operator rejects of a shape count against the rule that released it (canary-era rejects block activation; post-activation rejects demote). The replay proof runs in the test suite (`tests/test_operator_learner.py`) against the frozen Phase 5 proof log: a candidate mined from operator-released writes reaches shadow, climbs to active on rehearsal rounds, and then auto-decides the repeated writes, while the denied fetch-and-execute shape is covered by no release candidate. The live second proof run (`docs/proof-run-2-2026-11-02.md`, raw inputs in `docs/proof-run-2/`) shows the queue shrinking against Phase 5's baseline: session 1 queued 14 of 15 governed actions; session 2, with both learned rules active, queued 1 of 16 — an estimated ≈3 operator-minutes per 100 governed actions at the margin against ≈11 — and the planted fetch-and-execute was denied as a rejected twin and never executed. Slice 17 (the `any`-quotation accounting) completed spec 0.4: the token forms are enumerated in section 5, the effects walk descends into every token position except a literal's value, unknown dict forms are REFUSED(SPEC) with the form named, and C2 is stated in section 4 with the quotation case included — the Phase 4 hazard is closed in both implementations' terms (stock kernel refuses the form by name; the quarantined extension that keeps the form now accounts its verbs), with an adversarial battery in `tests/test_quotation_battery.py` and a dated addendum on the findings document. Tagged v0.4.0; suite at the tag: 266 passed, 7 skipped.

Phase 7 (complete): slice 18 — chain-head anchoring (spec section 15, spec 0.5). The log's hash chain proves self-consistency, not history: a holder could rewrite an entry and recompute the chain into a perfect forgery. Anchoring closes that with signed Ed25519 checkpoints of (log length, head hash, spec version), hash-chained per log and published outside the kernel's store in a separate public repo, [`SuperInstance/jacquard-anchors`](https://github.com/SuperInstance/jacquard-anchors), under an append-only publisher discipline. Verification (spec 15.5) reports one of four outcomes — verified, verified-to-anchor with the unanchored tail stated numerically, unanchored, or failed naming the first divergent checkpoint — never a bare boolean. The frozen Phase 6 proof log is anchored there at lengths 250 and 507, and the suite carries the attack as a fixture: the proof log with one decision outcome flipped and its chain recomputed passes internal chain verification and fails anchor verification at checkpoint 0 (`tests/data/forged/`, `tests/test_anchor.py`). The cold-verifier drill is `docs/anchor-drill.md`. See the anchoring section below.

Phase 7 (complete): slice 19 — the full TypeScript port. The TypeScript implementation in `conformance/ts/` now covers the whole kernel surface the golden vectors exercise: the original spec-only fold implementation (slice 8) plus `kernel.ts`, a deliberate port of the Python reference — dictionary and evaluator with computed effects and the slice 17 token-form refusals, the sequencer with the policy gate, the decision queue and the section 7.1 wait pump, sense computation (contention and authority included), the section 12.1 shape signature, and the section 15 anchor verifier (Ed25519 via Node's built-in crypto, no new dependency). The conformance checker runs **13 checks with zero SKIPs**: every golden-vector section is executed and compared, the shape signature is proven identical to the Python learner's over both proof-run corpora (8 + 27 queued decisions, item-for-item and by hash), and a cross-language drill — one 38-operation stream driven through both sequencers — produces **byte-identical logs and byte-identical verdicts** (`conformance/ts/cross-drill/`, evidence committed). The TS anchor verifier reproduces the Python tool's outcomes against the public anchors repo exactly, forged log included. Port scope, recorded in `conformance/ts/GAPS.md`: the machine profile and lifecycle machines, the WFQ scheduler, the booking profile, the learner pipeline beyond its signature function, and state bundles are not ported — the TS sequencer is a kernel without the lifecycle machines installed, which spec 10.4 defines as 0.1 behaviour. Tagged **v0.5.0**.

Phase 8, slice 21 (complete): beachhead 2 remainder — product integrity, spec 0.6. Three pieces. (1) **Key management as a product surface** (spec 15.3 rewritten): the anchor key is passphrase-encrypted at rest (passphrase via environment variable or tty prompt, never argv), and rotation with continuity was executed on the real anchors setup — the witness repo now carries a key registry (`keys.json`) with per-log validity windows, the retired key signed checkpoints 0–1, the successor signed checkpoint 2 over the same 507-entry prefix, and both single-key verifications fail at exactly the boundary while the registry schedule verifies 507/507 in both implementations. (2) **Sealed exports** (new spec section 16): designated fields are redacted in an export under commitments committed in the log before export; the anchored log is never altered; the export names the classes sealed and still verifies. Live run over the real proof log in `docs/slice21/`: 27 operator-identity fields sealed, export `verified_to_anchor` against the public anchors and `verified` against a demonstration checkpoint covering the seal entries, tamper with a sealed field detected. (3) **Compliance mapping** (`docs/compliance-mapping.md`): the built mechanisms mapped to SOC 2 CC6/CC7/CC8 and ISO 27001 A.8 control shapes, honestly labelled — a mapping, not a certification — with the gaps an auditor would still find named in the document itself. Suite at this slice: 306 passed, 7 skipped; TS checker 13 PASS, 0 SKIP.

Phase 8 (in progress): slice 20 — the Rust kernel port. The Rust implementation in `rust/` mirrors the TS port's layout and scope (a kernel without the lifecycle machines installed, spec section 10.4): canonical serialisation (own code, byte-exact), envelope, hash-chained log + fold, dictionary + evaluator with the form-agnostic effects walk, sequencer with the section 7.1 wait pump, section 11.3 senses, section 12.1 shape signatures, and the section 15 anchor verifier (Ed25519 via the `ed25519-dalek` crate; three dependencies in total). Its conformance checker runs the **same 13 checks with zero SKIPs**, and the cross-language drill now runs one 38-operation stream through **three** sequencers — Python, TypeScript and Rust — producing **byte-identical logs and byte-identical verdicts** (`conformance/ts/cross-drill/`, evidence committed). §12.1 signatures are identical to Python's on both real corpora. The port was built at spec 0.5 and aligned to spec 0.6 when slice 21 landed it mid-slice (the `seal` entry kind accepted and fold-inert, the registry-aware anchor verifier, checkpoint bodies naming 0.5 or 0.6). One spec divergence was found and recorded, not silently aligned: spec §1's string-escaping prose (ASCII `\uXXXX` form) contradicts the golden vectors and all three implementations, which prove the raw-UTF-8 reading; the Rust port follows the vectors, and the prose correction landed in slice 23 as spec 0.6 erratum 1 (prose only — no hash moved); the divergence is recorded in `rust/GAPS.md`. Crate metadata is publish-shaped under the name `jacquard-kernel` — the crates.io name `jacquard` is taken (an AT Protocol client library) — and nothing was published.

Phase 8, slice 23 (complete): packaging and the 1.0 release. Spec 0.6 erratum 1 corrects section 1's string-escaping prose to the raw-UTF-8 form the vectors and all three implementations always used (prose only; the seal derives from the version string, so no hash moved). An MIT LICENSE was added and is claimed in all three package metadata files. All three distributions are built and smoke-tested locally under the qualified name **`jacquard-kernel`** (the name `jacquard` is taken on PyPI, npm and crates.io): the Python wheel installs into a fresh venv and verifies the spec seal standalone, `cargo package` produces the crate, `npm pack` produces the tarball. The release-readiness checklist with its evidence is `docs/release-readiness-1.0.md`. **Tagged v1.0.0.** Registry publication itself — the first PyPI / crates.io / npm publishes — waits on the batched owner steps recorded there.

Not built yet: registry publication (owner steps batched in `docs/release-readiness-1.0.md`); the anchor-registry grammar fix (a key cannot yet declare it does *not* sign a log, so post-rotation logs verify via the explicit single-key form — the gpu-queue live log's checkpoints were verified that way, 91/91); a `register-window` verb (the witness-registry procedure is manual and documented in the anchors repo); the TS/Rust ports' remaining scope (kernels without the lifecycle machines installed, spec 10.4; the learner pipeline beyond the 12.1 signature; state bundles); a quarantine driver for the learner (demotion is real, quarantine stays an operator lever). See the builder's log for the current state and honest per-slice verdicts.

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
#    prints: executed <id>/action-0: exit 0 via subprocess -> state confirmed

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

## The ZCode adapter (Phase 5, slice 12 — built)

`adapters/zcode_hook.py` connects ZCode (a real coding-agent
host) to the kernel. Every tool call is translated into a
proposal in the coding-agent profile
(`src/jacquard/coding_agent.py`: four tool-class words whose
effects are computed, policy as data) and decided before it
runs: reads fast-path; writes, shell commands and network
actions queue for a batched, hash-bound operator decision; an
approval authorises exactly one retry of the identical action,
and the consumption is a log entry. Install, the queue story,
the host findings (plugin hooks run on this ZCode build;
configuration-file hooks do not), and the redaction posture
are in `adapters/zcode/README.md`; the live-run record is
`docs/slice12-live-run.md` and the measured comparison with
the host's native permission flow is
`docs/proof-run-2026-11-02.md`.

## Chain-head anchoring (Phase 7, slice 18 — built)

The hash-chained log proves a presented log is *self-consistent*.
It does not prove it is *the* history: whoever holds a log can
rewrite a middle entry, recompute the chain from that point on,
and present a forgery that chain verification accepts. Anchoring
(spec section 15) is the countermeasure: the operator
periodically signs a checkpoint — the log's length, the hash of
its last entry at that length, the spec version — and publishes
it **outside** the kernel's store, so history the operator cannot
silently rewrite witnesses the log's head.

- Tooling: `tools/jqanchor.py` (module `src/jacquard/anchor.py`,
  outside the kernel; its Ed25519 work via the `cryptography`
  package is that tooling's only non-stdlib dependency).
  `keygen` creates the operator key once, at
  `~/.jacquard/anchor-key.ed25519` (mode 0600, never in any repo;
  the tool refuses to overwrite it). `anchor` signs and stores
  the next checkpoint; `verify` needs only the public key, a
  checkpoint history and a presented log.
- Transport: checkpoints are transport-agnostic in the spec; the
  first transport is a dedicated public git repository,
  [`SuperInstance/jacquard-anchors`](https://github.com/SuperInstance/jacquard-anchors),
  one file per checkpoint (`checkpoints/<log_id>/<seq>.json`),
  one commit per checkpoint, adds only — never amend, rebase or
  force-push. Its README carries the operator public key and the
  verification summary. The frozen Phase 6 proof log
  (`docs/proof-run-2/kernel.jsonl`) is anchored there at lengths
  250 and 507 and verifies fully against a fresh clone.
- Outcomes, never a bare boolean: `verified` (tail 0),
  `verified_to_anchor` (anchored prefix and `unanchored_tail`
  reported as distinct numbers — an extension of an anchored log
  is this, not a forgery), `unanchored`, and `failed` naming the
  first divergent checkpoint (truncation below an anchored
  length is a failure, never a tail). Exit codes: 0, 0, 3, 1.
- The attack is a test fixture: `tests/data/forged/` holds the
  proof log with seq 100's outcome flipped and its chain
  recomputed (generator + provenance committed). It passes
  internal chain verification; anchor verification fails it at
  checkpoint 0. Both directions are asserted in
  `tests/test_anchor.py`.
- Cold-verifier drill: `docs/anchor-drill.md` — given only the
  public anchor repo, the spec and a presented log, an
  independent verifier reproduces all of the above, with exact
  expected values at every step.
- Honest bound (spec 15.6): anchoring proves a prefix existed in
  exactly that form no later than its checkpoint's publication,
  and detects post-anchor rewrites of the anchored prefix. It
  proves nothing about the unanchored tail, nothing about
  whether the decisions were wise, and not that a presented log
  is complete.

## Key management and sealed exports (Phase 8, slice 21 — built)

Two surfaces on top of anchoring, both spec-first (spec 0.6).

- **Keys** (spec 15.3): `jqanchor keygen` writes the operator
  key passphrase-encrypted (PKCS#8, best-available encryption)
  at `~/.jacquard/anchor-key.ed25519`, mode 0600; the passphrase
  comes from `JACQUARD_ANCHOR_PASSPHRASE` or a tty prompt —
  never argv, never logged. `jqanchor rotate` generates the
  successor and updates the witness repo's `keys.json` registry
  (per-log `signs_from` / `signs_until` windows that must
  partition each log's checkpoint sequence); verifiers take the
  schedule from `--pubkey`, from `--rotation-seq` +
  `--rotated-pubkey`, or from the registry via `--keys`, and
  the anchoring tool refuses to sign with a key outside its
  scheduled window. The checkpoint body itself did not change —
  continuity across rotation is the registry plus the
  `prev_checkpoint` hash chain.
- **Sealed exports** (spec 16): `tools/jqseal.py` — `seal`
  appends a seal entry to a copy of a log, committing to the
  redaction of a named field wherever it occurs (commitments
  are domain-bound hashes, or HMACs under an operator-held
  redaction key in `keyed` mode); `export` writes a prefix-only
  redacted document whose sealed values are replaced by their
  commitments; `verify` checks it against the anchors and
  reports the section 15.5 outcomes plus `seals_applied`,
  `seals_anchored` and `commitments_checked`. Redaction is a
  view, not a rewrite — and section 16.4 states its limits,
  including that a hash-mode commitment over a low-entropy
  value hides nothing. Live-run record: `docs/slice21/`.
- **Compliance mapping**: `docs/compliance-mapping.md` maps the
  built mechanisms to common control families and names the
  gaps (key custody as operated, no SIEM, no retention policy)
  in the document itself. It is a mapping, not a certification.
