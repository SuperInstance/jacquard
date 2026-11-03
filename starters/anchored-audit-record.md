# Starter kit: anchored audit record

**Use:** a record whose history a third party can verify
without trusting you — the "why was this allowed" evidence
for a small regulated operator. The hash chain proves a
log is self-consistent; anchoring proves it wasn't
rewritten.

**Proven by:** the public `SuperInstance/jacquard-anchors`
witness repo — the reference proof log anchored there
(the 507-entry log at checkpoints 0–2 across a key
rotation), and the attack fixture: the same log with one
decision flipped and its chain recomputed passes internal
verification and **fails** anchor verification at
checkpoint 0.

## 1. Build a log worth anchoring

Run any profile (the drill, a governed seat session, a
job queue) and keep its log. The log is the record; there
is no other state.

## 2. Anchor the chain head

```
python3 tools/jqanchor.py anchor --log <log> --anchor <anchor-dir>
#    signs (log length, head hash, spec version) with the
#    anchor key and appends the checkpoint to the anchor store
```

Publish the anchor store **outside** the kernel's store —
a separate repo, a separate host, a printout in a safe —
under an append-only discipline: new checkpoints only,
never edits. The fleet's witness repo is the pattern.

## 3. Verify as a stranger would

```
python3 tools/jqanchor.py verify --log <log> --anchor <anchor-dir>
#    verified | verified_to_anchor (with the unanchored tail
#    stated numerically) | unanchored | failed naming the
#    first divergent checkpoint — never a bare boolean
```

Try the attack yourself: copy the log, flip one decision
outcome, recompute the chain (`tools/jq.py` will still
pass internal checks), and watch verification fail at
checkpoint 0. That failure is the feature.

## 4. Share with fields withheld

When the record must travel with parts redacted, use
sealed exports, not edits:

```
python3 tools/jqseal.py seal --log <log> --classes <classes>
#    redacts under commitments committed in the log BEFORE
#    export; the anchored original is never altered; the
#    export names the classes sealed and still verifies
```

A tamper with a sealed field is detected by verification.

## Limits, honestly

- Anchor keys are passphrase-encrypted at rest; rotation
  with continuity is a procedure in the anchors repo, and
  the key-registry grammar (format
  `jacquard/anchor-keys/2`, null windows) is the part
  most often gotten wrong — read `docs/slice21/` first.
- Anchoring proves existence-at-publication through the
  publication record itself: the kernel has no trusted
  clock, so it does not fake a signed timestamp.
- Registry publication of the package itself is a pending
  owner step (`docs/PUBLISHING.md`); until then, installs
  are from git.
