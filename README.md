# Jacquard

A supervised runtime where untrusted producers submit proposals, a small auditable kernel decides what may change shared state or act on the world, learned behaviours are deployed under test, and every decision can be replayed from an append-only log.

Jacquard serves small teams and solo operators who run software agents — coding agents, job queues, automations — and need those agents' actions governed by a record they can defend: what was proposed, what was decided, by which policy, and why.

## What you can govern

- **Coding agents working in your repos** → the seat
  profile in `docs/QUICKSTART.md` and
  `starters/coding-agent-supervision.md`. In production on
  two devices: tool calls queue for batched, hash-bound
  decisions.
- **A shared GPU or expensive job queue** →
  `starters/job-queue-governance.md`. In production on a
  Jetson GPU server: unknown producers hold, jobs dispatch
  only through the kernel, outcomes journal back into the
  same log.
- **A shared schedule of machines** → the schedule profile
  in `docs/QUICKSTART.md`. In production on the fleet's own
  booking board: contention and rank are kernel senses,
  and a tie holds for an operator instead of silently
  winning.
- **A record a third party can verify** →
  `starters/anchored-audit-record.md`. Signed checkpoints
  are published in a public witness repo; a forged log
  fails verification at checkpoint 0.
- **Your own automations, solo** →
  `starters/batched-approvals-solo.md`.

## How it works

Producers (people, language models, programs, sensors) differ enormously in cost, latency, reliability and authority, but they all emit the same kind of thing: proposals. Jacquard separates proposing from deciding:

- **Proposals** arrive in a sealed envelope format and are never trusted. Each proposal's effects (what it would write, send, spend, or irreversibly do) are computed from the definitions it is built from.
- **Tentative state** holds undecided work as candidate sets, so nothing becomes shared truth just by being suggested.
- **The kernel** — a sequencer, an append-only hash-chained log, and a versioned policy gate — is the only part that can change committed state. It answers every submission with a verdict: accepted, decided, or refused with a named reason.
- **Approvals are batched.** Proposals that need a human decision go to a decision queue; everything else keeps moving. Asking never stalls the system.
- **Behaviour is extended by definition.** New behaviour enters as dictionary definitions composed from a fixed set of 26 primitives. A definition's effects are computed from its parts, not declared, so a definition cannot hide what it does. Learned behaviours (standing rules) are deployed through evaluation, shadow running, and staged activation, and can be revoked.
- **Everything replays.** Committed state is a fold of the log; any decision can be re-derived and checked.

Measured against incumbent practice on real workloads (full records in `docs/proof-run-2026-11-02.md`, `docs/proof-run-2-2026-11-02.md` and `docs/shadow-trial-2026-11-02.md`): in a shadow trial over a real booking board the kernel's decisions agreed with the incumbent process 88% of the time, with every disagreement classified; in governed coding-agent work, operator attention fell from ≈70 minutes per 100 governed actions under the host's native per-action permission flow to ≈11 in batched passes, and to ≈3 at the margin once learned standing rules were active — and the workload's one dangerous action was denied in batch review after the incumbent flow had waved it through.

## Install

Jacquard is installed **from git**. The package is not on PyPI / npm / crates.io yet; publication is prepared and waits on registry owner steps (`docs/PUBLISHING.md`):

```
git clone https://github.com/SuperInstance/jacquard
cd jacquard
```

Requirements: Python 3.11+ and git. The kernel and all operator tools are standard-library only (one exception: the anchoring tooling uses the `cryptography` package for Ed25519, and `import jacquard` never pulls it in). The test suite additionally needs `pytest`. Node is needed only for the optional TypeScript conformance suite; Rust only for that port.

`docs/QUICKSTART.md` takes you from the clone to your first governed action in about a minute. Concepts in meeting order: `docs/ONBOARDING.md`. Platform support and per-device notes: `docs/DEVICES.md`.

## Quickstart: the operator drill

The decision queue is the operator's surface. This drill runs it end to end — proposals in, queue presented, hash-bound batch decisions, actions executed, replay — in about a minute. From the repo root:

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

Success looks like: step 3 prints `approved <id>` / `denied <id>` and a following `queue` reports the queue empty; step 4 reports the action confirmed; step 5's replay shows the queued decision, the operator's decision, and the execution, in log order.

## The network service

The kernel is also reachable over HTTP, so a second machine can operate it: the same verbs as the operator CLI, against the same log, with the hash-binding rules unchanged. The service is standard-library only.

Run it (from the repo root, on the machine that owns the log):

```
python3 tools/jqserve.py --log /tmp/kernel.jsonl
# binds 127.0.0.1:8730 by default; --host / --port to change
```

Endpoints (JSON in, JSON out; every response that renders operator text carries it in a `text` field):

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

Queue presentation and replay are byte-for-byte identical to the CLI's output for the same log: both surfaces render through `src/jacquard/present.py`, and `tests/test_service.py` runs the operator drill through HTTP and the CLI on identical logs and diffs every rendering (and the resulting log files).

Decisions stay hash-bound over the wire: a `hash` that does not match the binding the queue presented fails with 409, prints the CLI's binding-mismatch line, and changes nothing. Successful batch items in a mixed batch still apply, exactly as the CLI processes the rest of a batch.

Senses are the owning kernel's *published* readings — values the kernel computed and wrote into its log, with their methods and `as_of_seq`. The service serves those publications; it never recomputes a reading (contention, authority, or any other) from the record on a consumer's behalf.

### Auth story, honestly

- **Loopback (the default).** Binding 127.0.0.1 trusts every local user of the host: anyone who can open a local TCP connection can operate the kernel. No token is required, because on loopback a token would only pretend to separate users the OS already shares the port with.
- **Non-loopback (LAN).** Requires BOTH the explicit `--allow-remote` flag AND a bearer token in the `JACQUARD_SERVICE_TOKEN` environment variable; without the token the service refuses to start on a non-loopback bind. When a token is configured it is checked on every request (`Authorization: Bearer <token>`); a missing or wrong token gets 401 and changes nothing.
- **What the token does:** keeps unauthorised machines on the LAN from operating the kernel, and nothing more. It is one shared secret — not per-user identity, not an audit of *who* decided (decisions are recorded as `operator`, as with the CLI).
- **What it does not do:** there is **no TLS**. The token and every payload cross the network in clear text, so anyone who can observe LAN traffic can read proposals and replay the token. Run it only on a LAN you trust, or inside a tunnel (SSH, WireGuard, Tailscale) — the token is a door lock, not an armoured car.

## Queue notifications

`tools/jqnotify.py` is the decision queue's tap on the shoulder: it folds the log, computes the current queue snapshot, and fires ONE batched summary when the queue waits at or beyond a configurable age or count. The summary carries counts by effect class, the oldest item's age, the total queue depth, and the queue snapshot hash — never a per-item listing by default (`--verbose` lists ids on the console only). It proposes nothing and approves nothing; decisions stay in the CLI/service.

```
python3 tools/jqnotify.py --log kernel.jsonl [--max-age-s N] [--max-count N] [--deliver]
```

- **Age is log time.** The kernel log has no wall-clock timestamps; its clock is the log itself (spec section 5, primitives P2/P6). An item's age is the distance in log entries between the decision entry that queued it and the newest substantive entry (the notifier's own records do not age the queue). `--max-age-s` (alias `--max-age`) is therefore in log entries. Every summary states its age mode (`log-entries`) and is recomputable from the log alone.
- **Thresholds** trip at or beyond the limit: oldest age `--max-age-s` (env `JQNOTIFY_MAX_AGE_S`, default 100 entries), depth `--max-count` (env `JQNOTIFY_MAX_COUNT`, default 5). `--check` reports whether a notification would fire without firing it.
- **Repeat suppression.** A state file (default `<log>.jqnotify-state.json`) records the last notified snapshot; a run re-fires only on a material change (new / changed queue contents, or the same oldest item strictly older on substantive log growth) — never on a poll loop over an unchanged queue.
- **Where firings land.** (a) A `queue-notification` checkpoint record appended to the kernel log itself, carrying the snapshot hash and the exact summary numbers — fold-transparent (the state hash is unchanged by it), and verifiable after the fact with `python3 tools/jqnotify.py --log kernel.jsonl --verify`, which re-folds the prefix before each record and recomputes its summary. (b) With `--deliver`, a Markdown drop committed to the fleet's agent-inbox repo under `verdicts/`, numbered sequentially in that folder's verdict format. Without `--deliver`, nothing leaves the machine.

## The ZCode adapter

`adapters/zcode_hook.py` connects ZCode (a coding-agent host) to the kernel. Every tool call is translated into a proposal in the coding-agent profile (`src/jacquard/coding_agent.py`: four tool-class words whose effects are computed, policy as data) and decided before it runs: reads fast-path; writes, shell commands and network actions queue for a batched, hash-bound operator decision; an approval authorises exactly one retry of the identical action, and the consumption is a log entry. Install, the queue story, the host findings (plugin hooks run on current ZCode builds; configuration-file hooks do not), and the redaction posture are in `adapters/zcode/README.md`; measured comparisons with the host's native permission flow are in `docs/proof-run-2026-11-02.md`.

## Chain-head anchoring

The hash-chained log proves a presented log is *self-consistent*. It does not prove it is *the* history: whoever holds a log can rewrite a middle entry, recompute the chain from that point on, and present a forgery that chain verification accepts. Anchoring (spec section 15) is the countermeasure: the operator periodically signs a checkpoint — the log's length, the hash of its last entry at that length, the spec version — and publishes it **outside** the kernel's store, so history the operator cannot silently rewrite witnesses the log's head.

- Tooling: `tools/jqanchor.py` (module `src/jacquard/anchor.py`, outside the kernel; its Ed25519 work via the `cryptography` package is that tooling's only non-stdlib dependency). `keygen` creates the operator key once, at `~/.jacquard/anchor-key.ed25519` (mode 0600, never in any repo; the tool refuses to overwrite it). `anchor` signs and stores the next checkpoint; `verify` needs only the public key, a checkpoint history and a presented log.
- Transport: checkpoints are transport-agnostic in the spec; the production transport is a dedicated public git repository, [`SuperInstance/jacquard-anchors`](https://github.com/SuperInstance/jacquard-anchors), one file per checkpoint (`checkpoints/<log_id>/<seq>.json`), one commit per checkpoint, adds only — never amend, rebase or force-push. Its README carries the operator public key and the verification summary. The reference proof log (`docs/proof-run-2/kernel.jsonl`) is anchored there at lengths 250 and 507 and verifies fully against a fresh clone.
- Outcomes, never a bare boolean: `verified` (tail 0), `verified_to_anchor` (anchored prefix and `unanchored_tail` reported as distinct numbers — an extension of an anchored log is this, not a forgery), `unanchored`, and `failed` naming the first divergent checkpoint (truncation below an anchored length is a failure, never a tail). Exit codes: 0, 0, 3, 1.
- The attack is a test fixture: `tests/data/forged/` holds the proof log with seq 100's outcome flipped and its chain recomputed (generator + provenance committed). It passes internal chain verification; anchor verification fails it at checkpoint 0. Both directions are asserted in `tests/test_anchor.py`.
- Cold-verifier drill: `docs/anchor-drill.md` — given only the public anchor repo, the spec and a presented log, an independent verifier reproduces all of the above, with exact expected values at every step.
- Honest bound (spec 15.6): anchoring proves a prefix existed in exactly that form no later than its checkpoint's publication, and detects post-anchor rewrites of the anchored prefix. It proves nothing about the unanchored tail, nothing about whether the decisions were wise, and not that a presented log is complete.

### Key management and sealed exports

Two surfaces on top of anchoring (spec sections 15.3 and 16).

- **Keys.** `jqanchor keygen` writes the operator key passphrase-encrypted (PKCS#8, best-available encryption) at `~/.jacquard/anchor-key.ed25519`, mode 0600; the passphrase comes from `JACQUARD_ANCHOR_PASSPHRASE` or a tty prompt — never argv, never logged. `jqanchor rotate` generates the successor and updates the witness repo's `keys.json` registry (per-log `signs_from` / `signs_until` windows that must partition each log's checkpoint sequence; the current registry format, `jacquard/anchor-keys/2`, also expresses a key that signs nothing for a given log). Verifiers take the schedule from `--pubkey`, from `--rotation-seq` + `--rotated-pubkey`, or from the registry via `--keys`, and the anchoring tool refuses to sign with a key outside its scheduled window. The checkpoint body itself does not change across a rotation — continuity is the registry plus the `prev_checkpoint` hash chain. Rotation has been executed on the production anchors setup: the retired key signed checkpoints 0–1, its successor checkpoint 2 over the same log prefix, and both single-key verifications fail at exactly the boundary while the registry schedule verifies the full log.
- **Sealed exports** (spec 16): `tools/jqseal.py` — `seal` appends a seal entry to a copy of a log, committing to the redaction of a named field wherever it occurs (commitments are domain-bound hashes, or HMACs under an operator-held redaction key in `keyed` mode); `export` writes a prefix-only redacted document whose sealed values are replaced by their commitments; `verify` checks it against the anchors and reports the section 15.5 outcomes plus `seals_applied`, `seals_anchored` and `commitments_checked`. Redaction is a view, not a rewrite — the anchored original is never altered — and section 16.4 states its limits, including that a hash-mode commitment over a low-entropy value hides nothing. A worked live run (27 operator-identity fields sealed in the reference proof log; the export verified against the public anchors; tamper with a sealed field detected) is recorded in `docs/slice21/`.
- **Compliance mapping**: `docs/compliance-mapping.md` maps the built mechanisms to SOC 2 CC6/CC7/CC8 and ISO 27001 A.8 control shapes and names the gaps an auditor would still find (key custody as operated, no SIEM, no retention policy, among them) in the document itself. It is a mapping, not a certification.

## Support matrix

Jacquard runs in production on the following platforms. The full per-device record is `docs/DEVICES.md`; the deployment evidence behind every row is `docs/slice30-device-matrix.md`.

| Platform | Profile | State |
|---|---|---|
| Linux server (x86_64) | Shared schedule (booking board), service host, governed-log home | In production |
| Jetson AGX Thor (aarch64) | GPU job-queue governance over a per-dispatch bridge | In production — no resident Jacquard process on the box, by design |
| WSL2 workstation (x86_64) | Coding-agent seat supervision (ZCode adapter) | In production |
| Jetson Orin Nano Super (aarch64) | Coding-agent seat supervision (ZCode adapter) | In production, with the tegra platform limitation below |
| Laptop (single-user, no server) | Solo automations, batched approvals | Prepared — not yet deployed |

Verification state: Python suite **340 passed, 7 skipped** on the reference platforms (Linux x86_64 and WSL2); TypeScript conformance **14 PASS, 0 SKIP, 0 FAIL**; Rust conformance **14 PASS, 0 SKIP, 0 FAIL**; the three implementations produce byte-identical logs and verdicts on the shared cross-drill, and identical shape signatures on the real corpora. Test counts are platform-dependent (see `docs/DEVICES.md`). The specification is version 0.6 (`spec/SPEC.md`).

## Known limitations

Stated plainly, as they stand:

- **Registry publication is pending.** The package is not on PyPI / npm / crates.io; installation is from git. Publication is prepared (packages built and verified locally under the qualified name `jacquard-kernel` — the name `jacquard` is taken on all three registries) and waits on owner steps (`docs/PUBLISHING.md`).
- **The laptop profile is not yet available.** The single-user profile is prepared and documented, but it has not been deployed on the fleet's laptop; that support-matrix row fills when a deployment record exists, not before.
- **On Jetson/tegra kernels, the executor's bubblewrap sandbox does not hold.** The sandbox-isolation test fails on those kernels although `bwrap` is present, so sandboxed execution is not guaranteed isolated there. Seat supervision and queue governance are unaffected; treat executor isolation on tegra as absent until the platform changes.
- **The TypeScript and Rust implementations are partial ports.** Each is a kernel without the lifecycle machines installed (spec §10.4 scope): the lifecycle machines and machine profile, the WFQ scheduler, the booking profile, the learner pipeline beyond the §12.1 signature, and state bundles are Python-only. Both ports pass the full conformance suite for the scope they implement, with zero skips.
- **The learner has no quarantine driver.** Regression demotion is automatic; quarantine remains an operator lever. The learner also learns only from operator decisions on queued shapes, per producer — it draws nothing from policy-allowed actions or expired items.
- **The consumption gate is built and tested but not active.** It prices job classes by their downstream use and activates only where a single job runs ≥ ~5 GPU-minutes; no such class exists in the reference deployment (its queue's complete history is seconds-scale), and it has not been demonstrated on manufactured work. Its pricing counts completed consumption only; a declared successor job is priced as ordinary production, because no successor/sentinel marker exists yet.
- **The service has no TLS and no per-user identity** (see the auth story above). Decisions are recorded as `operator`.
- **Anchoring has no trusted clock.** Checkpoints carry no signed timestamp; existence-at-a-time rests on the witness repo's publication record. Anchoring says nothing about the unanchored tail or the wisdom of decisions (spec 15.6). Witness publication is a manual procedure; there is no `register-window` verb.
- **Hash-mode sealed commitments hide nothing over low-entropy values** (spec 16.4); use keyed mode where the values are guessable.
- **MCode has no adapter.** Its bundles expose a plugin/hook surface (PreToolUse, PermissionRequest, PostToolUse, among others), but no MCode hook has been live-fired; MCode seats are supervised by governing what they emit (board rows, files, jobs), not their tool calls.
- **At equal authority rank, a challenger holds for an operator.** That is the standing tie disposition for contested bookings; the alternative (a named refusal on ties) is a one-line policy change that has not been taken.
- **A small number of spec ambiguities remain open** where the golden fixtures do not discriminate between readings; they are recorded in `conformance/ts/GAPS.md` and `rust/GAPS.md`.

## Repository layout

- `spec/` — the specification (SPEC.md, version 0.6) and golden vectors. The spec is the contract; implementations in any language must match the vectors byte-for-byte.
- `src/jacquard/` — the Python reference implementation of the kernel: the machine profile (`machines.py`), the seven lifecycle machine definitions (`lifecycles.py`), the WFQ scheduler (`scheduler.py`), senses (`senses.py`), the decision-model provider seam (`providers.py`), the learner (`learner.py`), state export bundles (`bundle.py`), and the booking application profile (`booking.py`). Also in the package, but outside the kernel: the anchoring tooling (`anchor.py`, spec section 15) — the package's only non-standard-library dependency (`cryptography`, for Ed25519) is confined to it, and `import jacquard` never pulls it in — and the sealed-export tooling (`sealing.py`, spec section 16, stdlib only). Beside the kernel sit the shared operator presentation (`present.py` — the queue/replay/status rendering both the CLI and the service use) and the network service (`service.py`).
- `adapters/` — adapters outside the kernel: decision-model providers (the kernel imports no provider-specific code), the sandboxed executor, the consumption-policy gate, the gpu-queue and booking-board bridges, and the ZCode coding-agent adapter (`zcode_hook.py` plus the installable surfaces in `zcode/`), which puts a coding agent's tool calls under kernel decision (the coding-agent profile itself is `src/jacquard/coding_agent.py`).
- `tools/` — operator and build tools: the operator CLI (`jq.py`), the service runner (`jqserve.py`), the anchoring CLI (`jqanchor.py`), the sealed-export CLI (`jqseal.py`), the queue notifier (`jqnotify.py`), the gpu-queue bridge (`jqgpu.py`), the booking-board CLI (`jqbook.py`), the golden-vector generator, the shadow-trial runner.
- `tests/` — unit tests plus the acceptance suite (a replay of a real GPU job-queue record through the kernel).
- `conformance/` — the TypeScript implementation and its conformance suite: a fold implementation written from the spec alone, plus `ts/kernel.ts`, a full port of the kernel contract for its scope (see Known limitations), its gap report, and the fixtures it folds. The TypeScript implementation reproduces the golden vectors and folds the 3,295-entry real replay log to the identical state hash.
- `rust/` — the Rust implementation of the same kernel contract and scope as the TypeScript port, with its own conformance checker (the same checks, zero skips), the three-kernel cross-drill, and publish-shaped crate metadata under the qualified name `jacquard-kernel` (see `rust/README.md`).
- `starters/` — one starter kit per proven use, each ending with the reader governing their own real task.
- `docs/` — user documentation (`QUICKSTART.md`, `ONBOARDING.md`, `DEVICES.md`, `PUBLISHING.md`, `compliance-mapping.md`) and the development record (below).

## Running the tests

```
python3 -m pytest -q
```

One executor test depends on bubblewrap holding on your kernel; on Jetson/tegra kernels it does not, and that single test fails there — a platform limitation (above), not a broken install.

## Development & history

Jacquard is specified before it is implemented: `spec/SPEC.md` is the contract every implementation is checked against. Versions and their changes are recorded in `CHANGELOG.md`. The complete development record — decisions, reasons, dead ends, per-slice reports and measured proof runs, in the order they happened — is `docs/BUILDERS-LOG.md` and the reports alongside it in `docs/`; `docs/PROGRAMME.md` is the programme narrative (what Jacquard is, the rulings behind it, and the verified build state), and `docs/USE-CASE-VOID-SCAN.md` is the market survey the build order came from. Operational rules that deployments depend on are stated where they apply; one is worth surfacing here: **a kernel log has one writer at a time** — submitters rebuild from the log rather than holding stale in-memory state.
