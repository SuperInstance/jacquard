# Rust port — gap and divergence notes (Phase 8, slice 20)

The Rust port's method is the slice 19 method: a deliberate
port of the reference behaviour (via `conformance/ts/kernel.ts`
and `jacquard.ts`, checked line by line against the Python),
never a spec-only reimplementation. Items below are the
places where that method met something worth recording.

## 1. SPEC DIVERGENCE — §1 string escaping (spec text vs vectors + both implementations)

- **Section:** spec §1, "Strings are escaped in the ASCII-safe
  form … every other character outside printable ASCII —
  including ALL non-ASCII characters — is escaped as `\uXXXX`
  with lowercase hex digits, astral characters as surrogate
  pairs."
- **Expected (per that text):** the canonical bytes of the
  fourth golden-vector entry (a checkpoint named `café-☃`)
  escape the non-ASCII characters, and its recorded hash is
  the hash of those escaped bytes.
- **Actual:** the recorded hash `0f77a6f4…` recomputes **only**
  under the raw-UTF-8 reading (Python `json.dumps(...,
  ensure_ascii=False)`, JS `JSON.stringify`): serialising with
  `\uXXXX` escapes hashes differently and check b fails. The
  Python reference (`src/jacquard/canonical.py`) and the TS
  port both emit raw UTF-8; TS GAPS item 3 records the same
  finding and its slice 19 closure ("CLOSED by check b")
  rests on it.
- **Minimal fixture:** `spec/vectors/vectors.json`, entries[3]
  — rebuild it under both readings; only raw UTF-8 reproduces
  the recorded hash.
- **Disposition:** the Rust port follows the vectors and the
  reference (raw UTF-8), as the slice brief itself states
  ("raw-UTF-8 string escaping"). The §1 prose is the outlier.
  Per this phase's spec discipline the spec is read-only for
  slice 20 — the correction belongs to slice 21, which owns
  spec edits: §1's string paragraph should be amended to the
  raw-UTF-8 rule both implementations and the vectors prove.
  Recorded here and in the builder's log; the spec was NOT
  edited by this slice. (Verified again against the landed
  spec 0.6, slice 21 at main 0b99a9e: the section 1 prose
  is carried into 0.6 unchanged, so the correction is still
  owed. The port was aligned to spec 0.6 after slice 21
  landed — see item 5's closing note — and its serialiser
  still follows the vectors' raw-UTF-8 rule, unchanged.)

## 2. Port scope (not a spec gap) — the TS boundary, mirrored

The Rust sequencer is, like the TS one, a kernel without the
lifecycle machines installed, which §10.4 defines as 0.1
behaviour. Not ported (fold-covered in check g where the TS
checker covers them): the machine profile and lifecycle
machines (§10), the WFQ scheduler and `buy_weight` (§11.1),
the booking profile (§11.4), the learner pipeline beyond its
§12.1 signature function (§§12.2–12.4), and state bundles
(§14). A `machine` envelope is refused REFUSED(SPEC) naming
this scope — the same deliberate, recorded divergence as the
TS port's, with the language name changed; it is identical
to no Python configuration's verdict for a *valid* machine
text, and it is recorded here so nobody mistakes it for
conformance on §10.

## 3. Inherited open items — TS GAPS 1, 2, 5, 15

The TS gap report's four honestly-open items stay open for
the same reason (no discriminating fixture exists), and the
Rust readings match the TS ones:

- **§1 key collation for astral/non-ASCII keys** (TS #1): the
  Rust serialiser sorts by Unicode code point explicitly
  (`compare_code_points`), as do both other implementations;
  no fixture carries such a key.
- **§1 integer range** (TS #2): Rust integers are i64
  internally; the canonical serialiser refuses integers
  outside ±(2^53−1) exactly as the TS port does (the Python
  reference accepts arbitrary precision — a latent divergence
  no fixture discriminates; the largest integer in any
  fixture or corpus is 10000).
- **Negative envelope validation** (TS #5): the Rust port
  implements the reference's ordered validation and the drill
  compares refusal verdicts for definitions and proposals,
  but no malformed-envelope vector exists.
- **Unknown-kind / malformed-body fold behaviour** (TS #15):
  both writers refuse unknown kinds; the fold stays total,
  undiscriminated by any vector.

## 4. Language notes

- **Ed25519:** verification uses ed25519-dalek's
  `verify_strict` (rejecting small-order points and
  non-canonical forms). The golden checkpoint, the public
  anchors history (verified 507/507), the forged fixture
  (failed at checkpoint 0) and the tampered-body probe all
  agree with the Python and TS verifiers.
- **Python equality:** Python's `True == 1` semantics are
  reproduced where the reference relies on them (`py_eq`),
  and Rust's native `==` is used only on type-homogeneous
  comparisons (verbs, outcomes, seq numbers, hash strings).
- **Floor division:** Python's `//` / `%` floor semantics are
  reproduced with `div_euclid` / `rem_euclid`.
- No divergence was found anywhere else: the checker passes
  13/13 and the cross-drill's 38-op stream produces
  byte-identical logs and verdicts in all three kernels on
  the first complete run of each.

## 5. Cross-lane note — the anchors history rotated mid-slice

During this slice, slice 21 (which owns key management and
spec 0.6) rotated the operator anchor key on the public
anchors repo: checkpoint 2 for the proof-run-2 log is signed
under a successor key and carries checkpoint-body spec
`jacquard/0.6`, with a `keys.json` registry recording the
windows (old key signs seq 0–1, successor from seq 2). This
port is chartered at spec 0.5: its verifier authenticates
the published 0.5 history (checkpoints 0–1) exactly as the
Python tool at v0.5.0 and the TS verifier do, and refuses
the 0.6 checkpoint at history authentication (body spec and
pinned key), which is the correct 0.5 behaviour. The library
`verify_anchor` already accepts an explicit key schedule
(mirroring `kernel.ts`); making the verifier 0.6-aware
(spec field, registry windows) is slice 21's deliverable,
not this slice's, and is recorded here so the boundary is
not mistaken for a Rust defect.

**Closing note (same day).** On the coordinator's update,
slice 20 aligned the port to spec 0.6 once slice 21 had
landed. The Rust verifier is now registry-aware in the TS
twin's form: `jacquard-verify-anchor --keys <registry>`
builds the pinned schedule from the registry windows for
the presented log's id, and checkpoint bodies naming spec
`jacquard/0.5` or `jacquard/0.6` are both accepted
(spec 15.1 (0.6)). Live evidence against the anchors repo
at 34f1c24: the frozen proof-run-2 log verifies **507/507**
under the registry (3 checkpoints checked, exit 0); a
retired-key-only run fails at checkpoint 2 and a
successor-key-only run at checkpoint 0 ("envelope pubkey
is not the pinned key for its sequence"); the forged
fixture fails at checkpoint 0 with `internal_chain_ok:
true` — identical to the Python tool and the TS twin.
