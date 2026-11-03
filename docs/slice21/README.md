# Slice 21 live run — sealed export of the proof-run log (2026-11-02)

Evidence for spec section 16, run on the Oracle against the
REAL anchors setup (public repo `SuperInstance/jacquard-anchors`
after the slice 21 rotation: checkpoints seq 0/1 under the
retired key, seq 2 under the successor, all for
`log_id 5f4bf2b4…db1814e`, the proof-run-2/kernel log).
The procedure is reproducible from the two public repos plus
this directory; the test-suite twin is
`tests/test_sealing.py::test_proof_run_log_sealed_export`.

## What was done

The frozen proof log (`docs/proof-run-2/kernel.jsonl`, sha256
`61d96a2a…3e3e3c` before and after — the source is never
modified) was copied to a scratch working log, and two `seal`
entries were appended with `tools/jqseal.py seal`:

- seq 507: 26 seals over `released_by`, class
  `operator-identity`, mode `hash`;
- seq 508: 1 seal over `rejected_by`, same class and mode.

(`decided_by` in this log names rules, not people, and was not
sealed.) The redacted export of the 509-entry working log is
`redacted-export.json` in this directory
(`seal_set_hash a6269ea3…c40e`).

## Verification outcomes (verbatim)

Export against the **public anchors** (`jqseal verify
--checkpoints <anchors clone> --keys <anchors clone>`):

```
outcome verified_to_anchor, anchored_length 507,
unanchored_tail 2, checkpoints_checked 3, seals_applied 27,
seals_anchored false, commitments_checked consistency, exit 0
```

The tail of 2 is exactly the two seal entries: against the
public history the seals are committed but not yet anchored,
and the result says so (`seals_anchored false`) instead of
rounding up.

A demonstration checkpoint — seq 3, length 509, signed by the
successor key over the working log — was issued into a scratch
store (the public checkpoints plus this one; the file is
`demo-checkpoint-000003.json` here, and belongs at
`checkpoints/5f4bf2b4…db1814e/000003.json` in a store laid out
like the anchors repo). Against that store, with the working
log supplied as the original:

```
outcome verified, anchored_length 509, unanchored_tail 0,
checkpoints_checked 4, seals_applied 27, seals_anchored true,
commitments_checked full, exit 0
```

Companion checks, same run:

- Unredacted working log, plain section 15.5 verification
  against the merged store: `verified`, 509 anchored, tail 0,
  4 checkpoints.
- Frozen original against the public anchors: `verified`, 507
  anchored, tail 0, 3 checkpoints.
- **Tamper:** one hex character of one sealed field's marker
  flipped (entry 23, `released_by`) → `failed`, stage `seals`,
  "entry 23 field 'released_by' marker does not match its
  committed seal", exit 1.

## Honest notes

The sealed values in this log are already public (the log is
published); this run demonstrates mechanics and verification,
and claims no confidentiality for them — spec section 16.4
states the general limit: a `hash`-mode commitment over a
low-entropy value hides nothing, and `keyed` mode exists for
the cases where that matters. The demonstration checkpoint is
evidence in this repo, not a publication in the anchors repo:
the public history deliberately stays at seq 2 / length 507 so
the frozen log's cold verification is unchanged.
