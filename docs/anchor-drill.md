# Anchor drill — verifying a Jacquard log as an independent third party

You are a fresh verifier. You trust nothing the log's holder tells
you. You have, or will fetch, exactly three things:

1. The **public anchor repository**: `SuperInstance/jacquard-anchors`
   — the witness history (spec section 15).
2. The **specification and reference verifier**: `spec/SPEC.md`
   (section 15 is the contract for everything below) and
   `tools/jqanchor.py`, both in `SuperInstance/jacquard`.
3. A **presented log** to verify. This drill uses the frozen
   Phase 6 proof log, `docs/proof-run-2/kernel.jsonl` in the
   kernel repo, as the presented log, plus the committed forged
   variant of it as the attack case.

You do **not** need any private key, any kernel state, or an
account anywhere. Every expected value below is stated exactly;
if your run differs, that difference is the finding — do not
adjust the drill to match your output.

## 0. Setup

```
git clone https://github.com/SuperInstance/jacquard.git
git clone https://github.com/SuperInstance/jacquard-anchors.git
cd jacquard
python3 -c "import cryptography; print(cryptography.__version__)"
```

The last command must print a version (the reference deployment
has 46.0.5). If it fails, `pip install cryptography` — it is the
anchor tooling's only non-standard-library dependency (spec
15.3); the kernel itself needs nothing beyond Python 3.11+.

The facts this drill verifies against (all public, all in the
anchor repo):

- Operator public key (hex, also in `jacquard-anchors/pubkey.txt`
  and its README):
  `1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5`
  In a real dispute you would confirm this hex with the operator
  through a second channel before relying on it (spec 15.3). For
  this drill, the value above is the pinned key.
- The presented log's identity (`log_id` = its genesis entry's
  hash, spec 15.2):
  `5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e`
- Two checkpoints exist for it, committed one per commit:
  - seq 0 — `log_length` 250, `head_hash`
    `9a3f33a27ecb5c2e77b59131672675379816a92a6221b5d1d8e821be808bb076`,
    anchor-repo commit `1f1309b7b85441747e49203b13baabfd9d5c71b6`;
  - seq 1 — `log_length` 507, `head_hash`
    `1e02bd867b777e165189d1adc0cc3a21227400ca2ee916003d38ce630740c8d5`,
    anchor-repo commit `89a6de3e12541be7dae2b1219ccc442cca35c79f`.

## 1. Look at the witness history

```
ls ../jacquard-anchors/checkpoints/5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e/
cat ../jacquard-anchors/checkpoints/5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e/000000.json
git -C ../jacquard-anchors log --oneline
```

Success looks like: exactly two files, `000000.json` and
`000001.json`. The file you printed is one line of canonical
JSON: a `body` (with the seq-0 values above and
`"prev_checkpoint": null`), a `pubkey` equal to the pinned key,
and a `sig`. The git log shows three commits — the repo opening
(README + `pubkey.txt`), then one commit per checkpoint, each
adding exactly one file. Any other shape (rewritten history,
extra files in a checkpoint commit) is a deviation to weigh, per
the anchor repo's README.

Optional spot check, no tooling: the checkpoint's claim is that
entry 250 of the log (line 250 of the file; entries are 1-per-line
in seq order) has the stated hash:

```
sed -n '250p' docs/proof-run-2/kernel.jsonl | python3 -c "import json,sys; print(json.load(sys.stdin)['hash'])"
```

must print the seq-0 `head_hash` above.

## 2. Verify the true log

```
python3 tools/jqanchor.py verify docs/proof-run-2/kernel.jsonl \
    --checkpoints ../jacquard-anchors \
    --pubkey 1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5
echo "exit=$?"
```

Success looks like exit **0** and JSON with exactly:
`"outcome": "verified"`, `"log_length": 507`,
`"anchored_length": 507`, `"unanchored_tail": 0`,
`"checkpoints_checked": 2`, `"internal_chain_ok": true`,
`"failure": null`. This is spec 15.5's VERIFIED: both published
checkpoints' signatures verify, the checkpoint chain recomputes,
and the presented log's heads at lengths 250 and 507 match.

## 3. The forgery: chain-valid, anchor-invalid

The kernel repo commits a forged variant of this log
(`tests/data/forged/proof-run-2-forged.jsonl`; its
`tests/data/forged/PROVENANCE.md` states how: the seq-100
decision's outcome was flipped `allow` → `deny` and the hash
chain recomputed from there).

First, confirm the kernel's own chain verification cannot tell:

```
python3 -c "
import sys; sys.path.insert(0, 'src')
from jacquard import Log
log = Log(path='tests/data/forged/proof-run-2-forged.jsonl')
print(len(log.entries), log.verify_chain())"
```

must print `507 True`. (The `Log` constructor itself raises on a
bad chain; reaching the print means it loaded.)

Now anchor verification:

```
python3 tools/jqanchor.py verify tests/data/forged/proof-run-2-forged.jsonl \
    --checkpoints ../jacquard-anchors \
    --pubkey 1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5
echo "exit=$?"
```

Success (of the mechanism) looks like exit **1** and JSON with
`"outcome": "failed"`, `"internal_chain_ok": true`, and a
`failure` naming `"stage": "prefix"`, `"checkpoint_seq": 0`,
`"expected_head"` = the seq-0 head from step 0, and
`"actual_head"` =
`de47470faa09d032ecd00229b9e68f8506354f950653b343fd2e80c91be75780`.
That is the slice's whole point, in one result: the forgery is
self-consistent and still caught, at the first checkpoint whose
prefix covers the rewrite.

## 4. The unanchored tail, exactly

Verify the true log against **only** the mid-log checkpoint:

```
mkdir -p /tmp/tail-check/5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e
cp ../jacquard-anchors/checkpoints/5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e/000000.json \
   /tmp/tail-check/5f4bf2b400dc3de3c6b4798028592650ca606facabf5c7a43e68ecd90db1814e/
python3 tools/jqanchor.py verify docs/proof-run-2/kernel.jsonl \
    --checkpoints /tmp/tail-check \
    --pubkey 1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5
```

Success looks like exit **0** with `"outcome":
"verified_to_anchor"`, `"anchored_length": 250`,
`"unanchored_tail": 257`. The tail is reported, not hidden: 257
entries are real but unwitnessed *by this history subset*. (An
extension of an anchored log lands in exactly this outcome —
same prefix, longer log — and is not a forgery.)

## 5. Truncation is a failure, not a tail

```
head -n 300 docs/proof-run-2/kernel.jsonl > /tmp/truncated.jsonl
python3 tools/jqanchor.py verify /tmp/truncated.jsonl \
    --checkpoints ../jacquard-anchors \
    --pubkey 1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5
echo "exit=$?"
```

Success looks like exit **1**, `"outcome": "failed"`, failure
`"checkpoint_seq": 1` — checkpoint 0 (length 250) passes against
the truncated log, then checkpoint 1 anchors length 507, more
than the 300 entries presented: anchored history is missing,
which section 15.5 makes a failure, never a "tail".

## 6. A log nobody witnessed

```
python3 tools/jqanchor.py verify docs/proof-run/kernel.jsonl \
    --checkpoints ../jacquard-anchors \
    --pubkey 1aa240acef0058b732e6093e3728e65a6d95a4178f77664ea92772bfb3072be5
echo "exit=$?"
```

The Phase 5 proof log has a different genesis, so no checkpoint
in the anchor repo applies to it. Success looks like exit **3**
with `"outcome": "unanchored"` — a statement about the witness
history, not an accusation against the log.

## Exit codes and outcomes, in one table

| exit | outcome | meaning |
|---|---|---|
| 0 | `verified` | every checkpoint passes; the whole log is anchored (tail 0) |
| 0 | `verified_to_anchor` | every checkpoint passes; `unanchored_tail` entries past the last anchored length are unwitnessed |
| 1 | `failed` | history authentication, the internal chain, or a prefix comparison failed; the JSON names which, and for a prefix failure the first divergent checkpoint |
| 3 | `unanchored` | no checkpoint in the supplied history names this log's genesis |
| 2 | — | tool refusal (missing key file, unreadable inputs, bad flags) — not a verification outcome |

## Trip points

- `--checkpoints` accepts the anchor repo's root, its
  `checkpoints/` directory, any directory holding checkpoint
  files, or a single checkpoint file's directory tree — it
  searches recursively for `*.json` checkpoint envelopes. If it
  finds files that are not checkpoint envelopes, verification
  fails at the history stage rather than ignoring them.
- The `--pubkey` argument is the trust decision. The `pubkey`
  inside each checkpoint envelope is checked *against* it; an
  envelope carrying a different key fails history authentication.
  Never copy the key out of the presented log's own materials.
- Verification never modifies the presented log or the checkpoint
  history. Anchoring (the write side) is a different verb
  (`jqanchor.py anchor`) and requires the operator's private key;
  a verifier neither has it nor needs it.
