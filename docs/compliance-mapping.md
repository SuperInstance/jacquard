# Compliance mapping — Jacquard mechanisms against common control families

**What this document is.** A mapping: for each control shape an
auditor commonly asks about, the Jacquard mechanism (as built
and specified) that speaks to it, and the artefact a reviewer
can inspect. It exists so that an operator evaluating Jacquard
for a governed environment can find the relevant machinery
without reading the whole spec.

**What it is not.** It is not a certification, an attestation,
or a claim of compliance with SOC 2, ISO/IEC 27001, or any
other framework. No audit has been performed. Several rows end
in a named gap — controls an auditor would still require that
Jacquard, as operated today, does not provide. Those gaps are
part of the document, not footnotes to it: see "Gaps an auditor
will find" at the end, which is the section to read first if
you are deciding whether to rely on this mapping.

Control references are to *shapes*: SOC 2 Trust Services
Criteria (CC6 logical access, CC7 system operations, CC8 change
management) and ISO/IEC 27001 Annex A technological controls
(A.8 in the 2022 edition, which absorbed most of the 2013
edition's A.12 operations controls). Exact criterion text
belongs to the frameworks; paraphrases here are summaries, not
quotations.

## Access control

*Auditor's shape: only authorised parties can perform
privileged actions; authorisation is specific, reviewable, and
revocable.* (SOC 2 CC6.1–CC6.3; ISO A.8.2, A.8.3, A.8.5.)

| Mechanism | Where | Evidence |
|---|---|---|
| Producers are untrusted by construction: they *propose*; the kernel's policy gate decides, and every decision is a log entry with its reasons. No producer holds standing authority to act directly. | Spec §§3, 7 | Any log: `decision` entries carry `producer`, `policy_version`, `outcome`, `reasons`. |
| Authority is ranked data, not identity alone: effective rank is `min(asserted, granted ceiling)`, and challenges between producers resolve by governed contention, not by who shouts loudest. | Spec §11.4 | `authority` sense readings in the log. |
| Approval of protected work is **hash-bound and one-shot**: the operator approves a specific proposal (its exact bytes), the approval is consumed by one execution, and release/reject/expire decisions are themselves log entries naming who decided (`released_by`, `rejected_by`). | Spec §§7, 12.2; Phase 5 adapter | Proof-run logs (`docs/proof-run-2/`): queued decisions, operator releases, learner training on the operator's labels. |
| The anchoring key — the one credential that can mint history-level evidence — is passphrase-encrypted at rest, unlocked per run, never passed on a command line; rotation is a published, hash-chained event and retired keys are refused by the tooling past their boundary. | Spec §15.3 (0.6) | Witness repo `SuperInstance/jacquard-anchors`: `keys.json` registry, rotation note, checkpoints seq 0–2 across the boundary. |

**Limits an auditor will note.** Producer "identity" inside a
log is a self-asserted string in an envelope; Jacquard governs
what a named producer may do, it does not authenticate the
human or process behind the name — that binding belongs to the
deployment (the reference adapter inherits the host agent's
identity). There is no access-review process, no joiner/mover/
leaver workflow, and no MFA anywhere in the reference
deployment: it is a single-operator system, and the controls
above are *mechanisms*, operated by one person. See gaps.

## Change management

*Auditor's shape: changes to logic that affects outcomes are
authorised, tested, recorded, and reversible; emergency changes
are distinguishable from normal ones.* (SOC 2 CC8.1; ISO
A.8.9, A.8.32.)

| Mechanism | Where | Evidence |
|---|---|---|
| Policy is data with a version: every decision records the `policy_version` that produced it, so "under what rules was this allowed?" is answerable per entry, not per era. | Spec §7 | `decision` entries in any log. |
| Learned standing rules have a **lifecycle, not a switch**: candidate → evaluated → shadow → canary → active, with **demotion** on regression, quarantine, and revocation as first-class transitions. A rule's stage is machine state, replayable from the log. | Spec §§10.4, 12 | Proof-run-2: rules mined, shadowed, promoted; the operator's release/reject labels retrain the learner (Phase 6). |
| Rule promotion is gated on evidence thresholds (support, dominance) computed from the log itself; the learner's origin-relative scoring after Phase 6 means a rule is judged against its own producer's baseline. | Spec §§12.3–12.4 | Learner entries + `docs/proof-run-2-2026-11-02.md`. |
| State that moves between kernels moves under **trust reset**: in an export bundle, standing rules re-enter at shadow regardless of their stage at export, credentials/authority/budgets are refused by name (`PROVENANCE`), and definition collisions with different content are refused. | Spec §14 | `tests/test_bundle.py`; bundle format `jacquard/state-export/1`. |
| The spec itself is versioned and sealed: envelopes carry `spec_seal`; checkpoints carry the spec version they were issued under; a version bump (0.5 → 0.6) regenerates the golden vectors and is recorded in the builder's log with reasons. | Spec §§1, 9, 15.1 | `spec/vectors/`, `docs/BUILDERS-LOG.md`, `CHANGELOG.md`. |

**Limits.** Nothing enforces a separation between the person
who changes policy data and the person who approves it — in
the reference deployment they are the same operator. There is
no change-advisory process, no scheduled-change window, and no
automatic rollback of a bad rule beyond the lifecycle's own
demotion path (which is evidence-driven and therefore acts
after outcomes are observed, not before).

## Audit logging and monitoring

*Auditor's shape: security-relevant events are logged
completely, protected against tampering, reviewable, and
retained; the logs answer "why was this allowed?" after the
fact.* (SOC 2 CC7.2–CC7.4; ISO A.8.15, A.8.16 — 2013: A.12.4.)

| Mechanism | Where | Evidence |
|---|---|---|
| The log is the record: append-only, hash-chained, and *complete by construction* for governed actions — proposals, decisions (with reasons), executions, operator decisions, rule changes, senses. State is a fold of the log, so any claimed state can be re-derived and checked. | Spec §2 | Any log + `Log.verify_chain`; state hash in `checkpoint` entries. |
| Tamper evidence beyond self-consistency: signed checkpoints of log prefixes are published to a **separate public witness repo**, so a rewrite-and-rechain forgery — which passes internal chain verification — fails against the anchors at the first divergent checkpoint. Demonstrated, not asserted: the committed forged fixture passes §2 and fails §15 at checkpoint 0. | Spec §15 | `SuperInstance/jacquard-anchors`; `tests/data/forged/` + its provenance; `docs/anchor-drill.md`. |
| Verification needs no trust in the log's holder and no private key; outcomes are never a bare boolean — `verified` / `verified_to_anchor` (both lengths stated) / `unanchored` / `failed` (first divergent checkpoint named). Two independent implementations (Python, TypeScript) produce identical outcomes on the real history. | Spec §15.5 | `tools/jqanchor.py`, `conformance/ts/verify-anchor.ts`. |
| Disclosure is governed too: sealed exports redact designated fields under commitments made in the log *before* export, name the classes sealed, and still verify; the anchored original is never altered by redaction. | Spec §16 (0.6) | `docs/slice21/` (live run over the real proof log); `tools/jqseal.py`. |
| The "why" is first-class: decision entries record outcome *and* reasons, the policy version, and — for queued work — the full stored request plus who released or rejected it. The queue batches operator decisions instead of blocking producers, so review happens in batches with the record open. | Spec §§7, 12.2 | Proof-run-2 operator timing: ≈3 operator-minutes per 100 governed actions at the margin (Phase 6 record). |

**Limits.** Verification is **on demand, not monitoring**:
nothing watches a log continuously, alerts on a failed
verification, or ships events to a SIEM. Timestamps are the
log's own sequence — Jacquard has no trusted clock by design,
so existence-at-a-time rests on the witness repo's git
publication record, and wall-clock correlation with external
systems is the deployment's problem. Retention is unaddressed
(see gaps).

## Cryptography and key management

*Auditor's shape: cryptographic controls are used where
claimed, keys are generated, stored, rotated, and retired
under a documented discipline.* (ISO A.8.24; SOC 2 CC6.7 in
part.)

| Mechanism | Where | Evidence |
|---|---|---|
| SHA-256 over a single canonical JSON form for every hash in the system; Ed25519 for checkpoints; HMAC-SHA-256 available for keyed seal commitments. The kernel is zero-dependency; signing code is confined to the anchoring tooling. | Spec §§1, 15, 16 | `src/jacquard/canonical.py`, `src/jacquard/anchor.py`. |
| Key lifecycle as built in spec 0.6: generation by the tool (refuses overwrite, refuses repo paths), passphrase-encrypted PKCS#8 at rest (mode 0600, outside every repo), passphrase via environment or tty prompt only — never argv, never logged — rotation with per-log validity windows in a published registry, retirement enforced by verifier schedule and by the anchoring tool itself. | Spec §15.3 | Witness repo history (rotation commits `df7f705`, `34f1c24`); `tests/test_anchor_keys.py`. |
| Compromise story is written down where the mechanism lives: what a key compromise does and does not poison, and the rotation-plus-note response. | Spec §15.3, §15.6 | Spec text; witness README. |

**Limits.** Key custody as *operated* is one operator, one
machine, one passphrase — no HSM, no dual control, no split
knowledge, no escrow. At the time of writing the live keys are
wrapped under an **interim passphrase** held in a mode-0600
file on the same machine pending the owner's re-wrap with a
passphrase of his own choosing; that is recorded here because
an auditor would (rightly) flag passphrase-and-key on one host
as a finding, and it is scheduled to be closed by the owner,
not by this document. Loss of both key and passphrase ends the
anchoring identity: continuity would restart under a new key
with a registry note — a documented path, never yet rehearsed.

## Gaps an auditor will find

Named plainly, in roughly the order an auditor would raise
them:

1. **Key custody as operated** — single operator, single host,
   no HSM or dual control; interim passphrase stored on the
   same machine as the keys until the owner re-wraps (above).
2. **No monitoring or alerting** — verification is a command a
   person runs. No SIEM integration, no alerting on failed
   verification, no continuous chain-checking service.
3. **No retention policy** — logs are append-only forever by
   design. There is no retention schedule, no archival tier,
   and no deletion story; that collides honestly with erasure
   duties (e.g. GDPR Article 17) for any personal data that
   reaches a log. Sealed exports (§16) reduce disclosure; they
   do not erase, and a hash-mode seal over a low-entropy value
   does not even hide it (§16.4).
4. **Identity is asserted, not authenticated** — producer names
   in envelopes are claims the deployment must bind to real
   principals; the reference deployment does not.
5. **Single-operator everything** — no segregation of duties,
   no access reviews, no change board. The mechanisms support
   review; the organisation around them is one person.
6. **No trusted time** — by design (the log is the clock);
   deployments needing wall-clock evidence must anchor it
   externally, as the witness repo's publication record does
   for checkpoints.
7. **Availability and recovery are out of scope** — one
   machine, no backups story specified for logs or keys, no DR
   rehearsal. (Log *integrity* survives copying — any mirror
   can verify — but nothing in the system makes the copies.)
8. **No independent assessment** — this mapping is the
   builder's own. The mechanisms have test suites and two
   independent implementations agreeing byte-for-byte on the
   kernel's vectors; that is engineering evidence, not an
   audit.

## How to check any row of this document

Clone `SuperInstance/jacquard` and
`SuperInstance/jacquard-anchors`. Run the test suite
(`python3 -m pytest -q`), the TypeScript checker
(`node conformance/ts/check.ts`), and the verifications in
`docs/anchor-drill.md` and `docs/slice21/README.md`. Every
mechanism named above is either in the spec sections cited or
it is not built — the README's built/not-built list is the
inventory of record, and this mapping claims nothing beyond
it.
