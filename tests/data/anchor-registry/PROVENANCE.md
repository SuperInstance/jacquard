# Vendored witness fixtures — provenance

Copied 2026-11-03 from the public witness repository
**SuperInstance/jacquard-anchors** for the slice-24 acceptance
tests (tests/test_anchor_registry_live.py), so the suite runs
offline. The live repository remains the source of truth; the
checkpoint envelopes bind the logs' head hashes, so any drift
between these copies and the logs under docs/ fails the tests
loudly rather than passing silently.

- `keys.json` — the witness registry republished under grammar
  `jacquard/anchor-keys/2` (slice 24): byte-identical to the /1
  document at anchors badd09d apart from the format string.
- `checkpoints/5f4bf2b4.../000000.json` … `000002.json` — the
  Phase 5/6 proof log's checkpoints (anchors commits 1f1309b,
  89a6de3, 34f1c24).
- `checkpoints/9cbf80c8.../000000.json`, `000001.json` — the
  gpu-queue live log's window-1 checkpoints (anchors commits
  bbc41c6, 4b339e9).

The logs themselves are the committed evidence copies:
docs/proof-run-2/kernel.jsonl (507 entries, sha256
61d96a2a4d223f4f97e3b6bd6235c3d9cc910ce9cdd71f3c4cb0309bad1e3e3c)
and docs/slice22/kernel.jsonl (91 entries, sha256
a0fa08c752de43c515ba9f8ec09fa26605d56e65f8cb9cc059a101fb06efd4a2).
