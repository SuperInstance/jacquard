# Jacquard — Rust implementation

The third implementation of the Jacquard kernel contract
(`spec/SPEC.md`, version 0.6), built in Phase 8 slice 20 as a
port of the TypeScript conformance port (`conformance/ts/`),
which itself ports the Python reference (`src/jacquard/`).
The layout mirrors the TS tree:

| Rust | TS | Covers |
|---|---|---|
| `src/value.rs` | (shared helpers) | the canonical value type: own JSON parser (insertion-ordered objects, exact integers), the section 1 canonical serialiser (own code, byte-exact: code-point key sort, raw-UTF-8 strings with the JSON-required escapes, integers refused outside ±(2^53−1)), Python-semantics helpers (`py_repr` / `py_eq` / `py_truthy` / `py_compare`) the refusal details depend on |
| `src/core.rs` | `jacquard.ts` | envelope validation + id (§3), entry construction, hash-chain verification, the fold and state hash (§2) |
| `src/kernel.rs` | `kernel.ts` | the 26 primitives, dictionary + evaluator with computed effects and the form-agnostic walk (§§4–5), policy gate (§7), the log, the sequencer with queue close operations and the §7.1 wait pump, producer records (§8) |
| `src/senses.rs` | (in `kernel.ts`) | sense computation (§11.3), contention and authority included, method strings verbatim |
| `src/signature.rs` | (in `kernel.ts`) | the §12.1 shape signature (shell skeleton via a POSIX shlex port, write extension, send host) |
| `src/anchor.rs` | (in `kernel.ts`) | the §15.5 anchor verifier: checkpoint history authentication, Ed25519 (via `ed25519-dalek`), the four outcomes |

Dependencies are exactly three crates: `sha2` (the §1 hash),
`ed25519-dalek` (§15 signatures), `flate2` (reading the `.gz`
conformance fixtures in the checker). Canonical serialisation
is this crate's own code, as the slice brief requires; no JSON
library touches a value anywhere.

Port scope is the TS port's scope, recorded in `GAPS.md`
beside this file: a kernel **without** the lifecycle machines
installed (spec §10.4 — that configuration is defined to
behave as the 0.1 kernel). The machine profile (§10), the WFQ
scheduler (§11.1), the booking profile (§11.4), the learner
pipeline beyond §12.1 (§§12.2–12.4) and state bundles (§14)
are fold-covered or out of scope exactly as in the TS port;
a `machine` envelope is refused with a SPEC verdict naming
that scope.

## Running the conformance checker

From the repository root (Rust stable, user-level install is
enough):

```
cargo run --release --manifest-path rust/Cargo.toml --bin jacquard-check
```

It prints one PASS/FAIL line per check — the same 14 checks
as `conformance/ts/check.ts` — and exits non-zero on any FAIL.
There are **no SKIP lines**: every golden-vector section is
executed and compared (seal, entry chain, checkpoint fold,
envelope id, the 3,295-entry replay log, the all-kinds full
log, dictionary stored forms, sequencer end-to-end state,
sense cases, the anchor checkpoint, §12.1 signatures over
both proof-run corpora against the Python-generated
expectations, and the §§4–5 token-form battery).

## The three-kernel cross-drill

```
python3 conformance/ts/cross-drill/cross_drill.py
```

drives the committed 38-operation stream through the Python,
TypeScript and Rust sequencers and compares all three logs
and all three verdict streams byte-for-byte, writing the
sha256s to `conformance/ts/cross-drill/EVIDENCE.txt` (the
orchestrator builds the Rust binary with cargo itself).

## The anchor verifier CLI

```
cargo run --release --manifest-path rust/Cargo.toml --bin jacquard-verify-anchor -- \
  docs/proof-run-2/kernel.jsonl --checkpoints <anchors-repo-clone> --pubkey <hex>
cargo run --release --manifest-path rust/Cargo.toml --bin jacquard-verify-anchor -- \
  docs/proof-run-2/kernel.jsonl --checkpoints <anchors-repo-clone> --keys <anchors-repo-clone>
```

prints the §15.5 result as JSON (the same eight fields as
`tools/jqanchor.py verify`) and exits 0 for
verified / verified-to-anchor, 1 for failed, 3 for
unanchored, 2 for a tool refusal. The `--keys` form reads
the witness key registry (`keys.json`,
`jacquard/anchor-keys/1` under the legacy reading, or
`jacquard/anchor-keys/2` with null windows — spec 15.3
erratum 2) — from the file itself or a
directory holding it — and builds the pinned key schedule
for the presented log's id from its `signs_from` /
`signs_until` windows, exactly as the TS twin and
`jqanchor verify --keys` do: against the live anchors repo
the frozen proof-run-2 log verifies 507/507 across the
rotation (retired key seq 0-1, successor from seq 2), while
either single key alone fails at exactly the boundary.
Checkpoint bodies naming spec `jacquard/0.5` or
`jacquard/0.6` are both accepted (spec 15.1 (0.6): the
anchor format did not change). See `GAPS.md` item 5.

## Crate metadata

`Cargo.toml` is publish-shaped: name, version aligned with
the release line (0.6.0), description, repository, keywords,
categories, pinned `Cargo.lock`. Two facts gate the actual
publish, both batched for slice 23's owner steps (see
`docs/BUILDERS-LOG.md`, slice 20):

- The crates.io name **`jacquard` is taken** — an AT Protocol
  client library (first published 2025-10-04, 25 versions,
  latest 0.12.2; checked against the crates.io API on
  2026-11-02). This package therefore carries the qualified
  name **`jacquard-kernel`**, which was free at the same
  check; the library crate is `jacquard_kernel`.
- The repository carries **no licence** (no LICENSE file, no
  licence metadata in `pyproject.toml`), so no licence is
  claimed here either; choosing one is an owner decision.
  `publish = false` stays set until slice 23 clears both.
