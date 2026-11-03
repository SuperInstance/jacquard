# Jacquard spec gap report — Phase 3 slice 8 (TypeScript, spec-only)

Written by the independent second-language implementer. Inputs read:
`spec/SPEC.md` and `spec/vectors/vectors.json` only (plus the
`conformance/replay-log.json.gz` fixture for checks e/f). No reference
implementation source was consulted; every item below is a place where
the spec text alone underdetermines the implementation — two careful
implementers, each reading only the spec, could diverge.

Each item: spec section · the ambiguity in one sentence · the reading
chosen in `jacquard.ts` · which conformance check (if any) would catch
a wrong choice.

---

## 1. §1 — Key-sort collation is unspecified
- **Ambiguity:** "keys sorted" does not state the collation (Unicode code
  point, UTF-16 code unit, locale, or byte order differ outside ASCII /
  for astral characters).
- **Chosen:** lexicographic by Unicode code point.
- **Caught by:** b, e — but only for the keys actually present in the
  fixtures (all ASCII). A non-ASCII or astral key would diverge silently.

## 2. §1 — Integer range is unbounded; host languages are not
- **Ambiguity:** values are "integers" with no stated range, but a JS
  number loses exactness beyond 2^53, and integers ≥ 1e21 serialise in
  exponent form by default.
- **Chosen:** reject non-safe integers at serialisation time (throw)
  rather than emit possibly-wrong canonical bytes.
- **Caught by:** none — the largest integer in either fixture is 3295.

## 3. §1 — String escaping beyond "UTF-8" is unspecified
- **Ambiguity:** the canonical form does not say whether non-ASCII
  characters are emitted raw (UTF-8) or `\uXXXX`-escaped, nor which
  short escapes (`\n` vs `\u000a`) are used for control characters.
- **Chosen:** raw UTF-8 for non-ASCII (JSON.stringify behaviour);
  JSON short escapes where they exist, `\u00xx` otherwise.
- **Caught by:** none — verified: neither fixture contains a single
  non-ASCII character, so this choice is completely untested by the
  golden vectors.

## 4. §3 — "Hash of the string" for the spec seal is ambiguous
- **Ambiguity:** §1 defines the hash of a *structure* via canonical
  bytes, so "the hash of the string `jacquard-spec/0.2`" could mean the
  SHA-256 of the raw string bytes or of its canonical JSON form
  (with surrounding quotes).
- **Chosen:** raw UTF-8 bytes of the bare string.
- **Caught by:** a — decisively (the quoted reading gives a different
  seal and fails).

## 5. §3 — Envelope validation rules are not enumerated
- **Ambiguity:** §3 shows the envelope shape but never states the
  validation rules: whether extra keys are forbidden, whether `id`
  must be non-empty, or whether kinds outside the three listed are
  refused at envelope level.
- **Chosen:** allow extra keys; require the stated fields with the
  stated types, `v` = 1, kind in {proposal, definition, machine}, and
  `spec_seal` equal to the computed seal.
- **Caught by:** d only exercises one valid envelope; no negative
  envelope vector exists.

## 6. §2 / §9 — The entry hash's input, and the vectors' entry format, are implicit
- **Ambiguity:** stored entries carry a `hash` field and §2 says the
  entry hash is "the hash of the entry", without stating that the
  `hash` field itself is excluded from the hashed object; and the
  vectors file's entry records omit `prev` and `spec` entirely, so
  rebuilding them requires inferring both from §2's prose.
- **Chosen:** hash the object {seq, prev, kind, body, spec} (no `hash`
  key); when rebuilding vectors, supply `prev` from the chain and
  `spec` = "jacquard/0.2".
- **Caught by:** b and e — decisively (all 3 vector hashes and all
  3,295 replay hashes recompute under exactly this reading).

## 7. §2 / §7 — The queued decision's outcome literal and the release shape are unstated
- **Ambiguity:** §2 says proposals whose decision outcome was "`queued`"
  enter the queue, §7's gate returns the outcome "`queue`", and neither
  section states the outcome string actually written in the decision
  entry, the field naming the proposal id, or the shape of a releasing
  decision.
- **Chosen:** accept both `"queued"` and `"queue"` as the queueing
  outcome; key the queue by the body's `proposal_id` and store the
  full decision body; close items when a later decision body carries
  `releases`, `rejects`, or `expires` naming the proposal id (§10.4
  pins the latter two field names, and `releases` by symmetry).
- **Caught by:** none — every decision in the replay fixture has
  outcome `allow`; no fixture exercises queueing, release, rejection,
  or expiry.

## 8. §2 / §11.3 — Sense entry body vs. the §11.3 reading shape conflict in presentation
- **Ambiguity:** §11.3 describes a sense entry "whose value is
  {"value", "method", "as_of_seq"}", while §2 says senses fold to "the
  latest published reading per sense name" without saying whether the
  folded reading is the body's `value` field, the whole body, or a
  {value, method, as_of_seq} object — and the fixture sense bodies
  ({name, producer, value}) match none of §11.3's wording directly.
- **Chosen:** the folded reading is the entry body's `value`, verbatim.
- **Caught by:** c and f — decisively. (The whole-body and wrapped
  readings were tried against both fixtures and produce different
  state hashes.) The spec should reconcile §11.3's wording with the
  actual entry body.

## 9. §10.3 — The folded representation of a machine instance is unstated
- **Ambiguity:** §2 says `machine_instances` holds "the current state
  of every machine instance" and §10.3 says an instance's state is the
  `to` of its latest created/taken entry, but neither says whether the
  folded value is the bare state-name string or an object (e.g. also
  recording the machine name).
- **Chosen:** the bare state-name string, keyed by instance id.
- **Caught by:** none — neither fixture contains a single `transition`
  entry, so machine-instance folding is entirely unverified by the
  golden material.

## 10. §11.2 — `budget` and `price` entry body schemas are never stated
- **Ambiguity:** §11.2 describes grants, purchases and posted prices
  but never gives the entry bodies: the field names for the producer,
  the delta, the resource, and the price are all left to guesswork.
- **Chosen:** budget body {producer, delta} (delta added to the
  balance); price body {resource, price} (posted price replaces).
- **Caught by:** none — neither fixture contains a `budget` or `price`
  entry; budget/price folding (and the §11.2 spend-cost rule, which at
  least is stated precisely) is unverified end to end.

## 11. §12 — The folded value stored per rule id is unstated
- **Ambiguity:** §2 says `rules` holds "standing rules by id" without
  saying whether the value is the full rule entry body or a subset
  (e.g. without scores/support fields).
- **Chosen:** the full rule entry body, keyed by its `rule_id`.
- **Caught by:** none — neither fixture contains a `rule` entry.

## 12. §14 — The `import` entry body schema is never stated
- **Ambiguity:** §14 says config unit values are applied "under an
  `import` entry recording the bundle hash and the export provenance"
  but never gives that entry's body, so a folder cannot know where the
  unit values (or bundle hash) sit in it.
- **Chosen:** if the body carries unit values under `units` (or
  `config.units`), apply them as writes; otherwise an import entry
  changes nothing.
- **Caught by:** none — neither fixture contains an `import` entry.

## 13. §§2–14 — Entry body schemas in general are mostly absent from the spec
- **Ambiguity:** apart from checkpoint (§2), machine (§10), transition
  (§10.3) and rule (§12, partial), the spec never states the body
  schema of any entry kind — `decision` (outcome / proposal_id /
  policy_version / reasons), `execution` (applied / producer /
  proposal_id / uses), `sense`, and `proposal` bodies are knowable
  only from the fixtures, not from the contract.
- **Chosen:** fold using the field names observed in the fixtures
  (`applied` request list for execution, `proposal_id`/`outcome` for
  decision, `name`/`value` for sense).
- **Caught by:** e and f verify the *fixture* field names; nothing in
  the spec text would let a spec-only implementer derive them.
  This is the report's most consequential item: §9 claims an
  implementation reproducing the vectors "implements sections 1–5
  compatibly", but the fold-critical schemas live in §§7/11 territory
  and only in the data.

## 14. §2 — When a budget key comes into existence is unstated
- **Ambiguity:** the folded `budgets` map is "per-producer account
  balance", without saying whether a producer appears after a first
  spend with no prior grant (balance negative), after a zero grant,
  or only once a grant lands.
- **Chosen:** a producer's key is created by its first budget entry or
  first applied spend, whichever comes first.
- **Caught by:** none — no fixture contains a budget or spend.

## 15. §2 — Fold behaviour for unknown kinds / malformed bodies is unstated
- **Ambiguity:** the fold's contract for an entry whose kind is not in
  the §2 list, or whose body lacks the fields its kind needs (e.g. a
  definition entry whose definition has no name), is never stated —
  refuse the log, skip the entry, or fold partially are all open.
- **Chosen:** skip the offending entry's effect (fold is total);
  chain *verification* (seq/prev/spec/hash) remains strict.
- **Caught by:** none — all fixture entries are well-formed.

---

## Result note

No check failure is attributed to the spec in this run: checks a–d
pass under the readings above, and checks e/f were verified against
the replay fixture with a scratch prototype of the identical
algorithms earlier in this session (all 3,295 hashes recompute;
folded state hash matched `expected_state_hash`). The gaps above are
therefore *latent* divergences — places where the fixtures happen not
to discriminate between readings — not observed failures. Items 9–14
share one root cause worth fixing first: the fixtures contain only 4
of the 12 entry kinds (definition, decision, execution, sense), so
eight kinds' fold rules are specified, if at all, only in prose that
omits the schemas and representations a second implementer needs.

## 16. §11.3 / §9 — Sense computation is kernel work, not fold work (Phase 4, spec 0.3)

- **Ambiguity:** spec 0.3 adds a `senses` section to the golden
  vectors: entry lists plus a subject, with the expected reading
  {value, method, as_of_seq}. A reading is a *published value*
  computed by a kernel over the entry prefix up to its
  as_of_seq (the contention and authority methods scan entries
  and committed units with stated filters); the fold itself only
  stores published readings verbatim, so no fold rule in the
  spec derives a reading from a subject.
- **Chosen:** sense computation is declared out of this
  checker's fold scope: the checker reports the section as
  SKIP (`vectors.senses`). Sense *entries* still fold exactly
  as before (the body's `value`, verbatim — see #8), and
  checks e/f/g cover logs containing them.
- **Caught by:** the Python suite — tests/test_vectors.py
  verifies every senses case via fold + compute_sense.

## 17. §§4–5 — Token-form accounting (Phase 6, spec 0.4)

- **What changed:** spec 0.4 states the effects-accounting rule
  for dictionary bodies: the token forms are exactly `{"lit"}`,
  string, and `{"if"/"else"}`; the effects walk descends into
  every token position of every form except a literal's value
  (data, never tokens); a dict token of any other form is
  REFUSED(SPEC) at definition time with the form's key named;
  and C2 (computed effects = the union over the expansion) is
  stated with the quotation case included — a form quoting a
  body for later evaluation, if a future version defines one,
  has its body accounted at definition time.
- **Chosen:** unchanged scope — this checker implements the
  fold, not the evaluator, so `vectors.definitions` remains
  SKIP, now under the 0.4 rule as well: a future TS evaluator
  must implement the descending walk and the named SPEC
  refusal, and the Python battery
  (tests/test_quotation_battery.py) is the reference behaviour
  until then. One reading recorded for that implementer: for
  a hybrid dict carrying several keys, the reference names
  the first key in sorted order in the refusal detail; the
  spec's "the form's key" is unambiguous for the single-key
  forms the hazard actually uses.
- **Caught by:** the Python suite — the adversarial battery
  (original probe case both ways, nested quotations,
  quotation in an if branch, composition smuggling, hybrid
  forms, literal-carried verb-shaped data, forged-body
  evaluation) plus the re-aimed probe-(f) tests.

## 18. §15 — Chain-head anchoring is verifier work, not fold work (Phase 7, spec 0.5)

- **What changed:** spec 0.5 adds section 15: signed Ed25519
  checkpoints of (log length, head hash, spec version), published
  outside the kernel's store, with a stated verification procedure
  whose outcomes are VERIFIED / VERIFIED-TO-ANCHOR (anchored
  prefix and unanchored tail reported separately) / UNANCHORED /
  FAILED naming the first divergent checkpoint. The golden
  vectors gain an `anchor` section: one checkpoint over the
  vector entry chain under a published test key (seed recorded in
  the vectors; Ed25519 is deterministic, so the signature is a
  stable vector).
- **Chosen:** unchanged scope — this checker implements the
  fold, not the verifier, so the checker reports the section as
  SKIP (`vectors.anchor`), exactly as for senses (§11.3, #16).
  Version constants and the seal were aligned to 0.5 in this
  slice, and both conformance fixtures (full-log, replay-log)
  were regenerated under the 0.5 kernel, so checks a–g stand as
  before. A future full TS port (slice 19) must implement §15.5
  in full: history selection by genesis `log_id`, the checkpoint
  hash chain (`prev_checkpoint`), pinned-key signature
  verification, and the four-outcome report — never a bare
  boolean.
- **Caught by:** the Python suite — tests/test_vectors.py
  verifies the anchor vector's signature with the `cryptography`
  package directly, and tests/test_anchor.py exercises the
  reference verifier end to end, including the forged-log fixture
  (a rewrite-and-rechain forgery that passes internal chain
  verification and fails anchor verification at the first
  divergent checkpoint).

---

## Slice 19 closures (2026-11-02) — the full TS port

Slice 19 ported the Python reference into `kernel.ts` (see the
builder's log for the method note: this file's earlier items
were written by a spec-only implementer; the port is a port,
and the readings below are now the *reference* readings, tested
against the reference behaviour directly). The checker now runs
13 checks with zero SKIP lines. Item by item:

- **16. Sense computation — CLOSED.** `kernel.ts` computes the
  contention and authority senses (and the other built-ins)
  over entry prefixes; check `vectors.senses` compares every
  case's full reading {value, method, as_of_seq} against the
  vectors, exactly as `tests/test_vectors.py` does.
- **17. Token-form accounting — CLOSED.** The TS dictionary
  implements the form-agnostic walk and the named SPEC refusal;
  check `i. token-form battery` runs the stock-kernel half of
  the Python adversarial battery (original probe, nested
  quotation, quotation in an if branch, composition smuggling
  via refusal, both hybrid forms, forged body at evaluation,
  literal-carried data) against it, and the cross-language
  drill's stream contains the probe definition, refused with a
  byte-identical verdict detail in both languages. The hybrid
  reading recorded in the original item (first key in sorted
  order names the refusal) is the reference's `_form_key` and
  the port reproduces it.
- **18. Chain-head anchoring — CLOSED.** `kernel.ts` implements
  §15.5 in full (history selection by genesis `log_id`, the
  `prev_checkpoint` hash chain, pinned-key Ed25519 verification
  via Node's built-in crypto, the four-outcome report) plus a
  CLI twin of `jqanchor verify` (`verify-anchor.ts`). Check
  `vectors.anchor` verifies the vector checkpoint both ways
  (signature valid over the body, invalid over a tampered body)
  and runs the procedure over the vector chain. Against the
  public anchors repo the TS verifier reproduces the Python
  outcomes exactly: true proof log `verified` (507/507, tail
  0), forged fixture `failed` at checkpoint 0 with
  `internal_chain_ok: true`, tail subset 250/257
  `verified_to_anchor`, truncation `failed` at checkpoint 1,
  Phase 5 log `unanchored`.

Closures among items 1–15, only where a check now genuinely
discriminates the reading:

- **3. String escaping — CLOSED by check b.** The vector chain's
  fourth entry carries the non-ASCII checkpoint name
  (`café-☃`); its recorded hash recomputes in TS only under the
  raw-UTF-8 reading (an ASCII-escaped serialisation hashes
  differently and fails). The earlier "caught by: none" was
  written against the replay/full fixtures; the golden entries
  themselves discriminate, and did since the entry was added —
  recorded here as a correction to that line.
- **7. Queued outcome literal / release shape — CLOSED by the
  cross-language drill.** The drill stream queues four
  proposals and closes them by release, rejection and expiry;
  both sequencers emit byte-identical decision bodies
  (`queued` literal, `releases`/`rejects`/`expires` plus
  `released_by`/`rejected_by`/`expired_by`), and the TS fold
  was aligned to the reference's if/elif chain (a queued body
  enters; only a non-queued closing body removes).
- **10. Budget/price body schemas — CLOSED by the drill + g.**
  The drill's grant and price ops make both sequencers *emit*
  `budget` {producer, delta, by} and `price` {resource, price,
  by} entries byte-identically, and check g already pinned the
  fold reading of such entries from the Python-generated
  full log.
- **11. Folded value per rule id — CLOSED by the drill.** The
  stream appends one standing-rule record identically in both
  kernels; the drill's closing checkpoint state hash is
  byte-identical, which holds only if the folded `rules` value
  is the `rule` object itself in both folds.
- **13. Entry body schemas — CLOSED IN PART.** The port +
  drill now pin, end to end (emission and fold, byte-compared
  against the reference): proposal-submission outcomes for
  decision, execution, definition, sense, budget, price and
  rule bodies. Machine, transition and import bodies remain
  fold-pinned only (check g), because the TS sequencer does
  not emit them (see port scope below).
- **14. Budget key existence — CLOSED by the drill.** The
  stream's final proposal is an operator spend with no prior
  grant; both folds create the key from the spend (balance
  −6 at price 3), inside the byte-identical log and its
  closing state hash.

Items **1, 2, 5, 15 remain open**, honestly: no fixture yet
contains an astral or non-ASCII *key* (1), an integer near
2^53 (2), a negative envelope-validation case (5 — the port
implements the reference's ordered validation and the drill
compares refusal verdicts for definitions and proposals, but
no malformed-envelope vector exists), or an unknown-kind /
malformed-body log entry (15 — both writers refuse unknown
kinds; the fold stays total, undiscriminated by any vector).

### Slice 19 port scope (not spec gaps)

The TS port covers §§1–5, 7 (+7.1), 11.2–11.3, 12.1 and 15.5.
Not ported, by the slice's charter: the machine profile and
lifecycle machines (§10 — the TS sequencer is a kernel without
them installed, which §10.4 defines as 0.1 behaviour, and the
drill's byte-identity holds under exactly that configuration),
the WFQ scheduler and `buy_weight` (§11.1), the booking
profile (§11.4), the learner pipeline beyond its signature
function (§§12.2–12.4), state bundles (§14), and the service /
CLI surfaces. `submit` of a `machine` envelope in TS returns a
REFUSED(SPEC) verdict naming this scope instead of a machine
check — a deliberate, recorded divergence from a Python kernel
*with* the profile installed, and identical to no Python
configuration's verdict for a *valid* machine text; it is
recorded here so nobody mistakes it for conformance on §10.
