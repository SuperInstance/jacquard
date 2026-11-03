# Forged-log fixture — provenance

`proof-run-2-forged.jsonl` is a **deliberately forged** variant of
the frozen Phase 6 proof log (`docs/proof-run-2/kernel.jsonl`),
committed as the slice-18 acceptance fixture for chain-head
anchoring (spec section 15). It is test evidence, not a record:
nothing in it happened.

## How it was forged

By `make_forged.py` beside this note (deterministic; re-running
it reproduces the fixture byte-for-byte):

1. Entry **seq 100** of the true log — a `decision` entry with
   outcome `allow`, the operator's release (`released_by:
   operator`, `releases` set) of proposal
   `495d40460dfc5fa12e44c1ffa86dfdc33bcc8a8a1ffd4eb374597bdd9fffcc61`
   — has its `outcome` flipped to `deny`. Nothing else in the
   entry is changed.
2. The internal hash chain is recomputed from seq 100 on: every
   later entry's `prev` is relinked and every hash recomputed
   over `(seq, prev, kind, body, spec)`, preserving each entry's
   recorded spec (`jacquard/0.4`).

## Why this fixture exists

The forged log is **fully self-consistent under the kernel's own
chain verification** (spec section 2): `Log(path=...)` loads it
without complaint and `verify_chain()` returns true. That is the
attack anchoring exists to defeat — a holder of the log rewriting
history and re-chaining it. Section 2 alone cannot distinguish
this file from the true log; the head of the true log at the
first anchored length (250) is
`9a3f33a27ecb5c2e77b59131672675379816a92a6221b5d1d8e821be808bb076`,
and the forged log's head at the same length differs, so anchor
verification against the published checkpoints
(`SuperInstance/jacquard-anchors`) must FAIL, naming checkpoint
seq 0 as the first divergent checkpoint.

`tests/test_anchor.py` asserts both directions against this
fixture: internal chain verification passes; anchor verification
fails at checkpoint 0. If either assertion ever flips, the
fixture or the mechanism has broken — treat it as a finding, not
a test to update.
