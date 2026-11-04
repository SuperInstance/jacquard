# Jacquard specification — version 0.7

This document is the contract. Conforming implementations must
reproduce the golden vectors in `spec/vectors/` exactly. The Python
code in `src/jacquard/` is the reference implementation of this
version.

## 1. Canonical serialisation

All hashed or stored structures use one canonical JSON form:

- UTF-8, keys sorted, separators `,` and `:` (no whitespace).
  Key sorting is lexicographic by Unicode code point.
- Values are restricted to: null, true, false, integers, strings,
  arrays, objects. **No floating-point numbers.** Quantities that
  would be fractional are integers in a stated unit (weights are
  milli-units, durations are milliseconds).
- Integers are mathematical integers, but cross-language
  conformance is guaranteed only in the safe range
  -(2^53 - 1) .. 2^53 - 1: an implementation that cannot
  represent an integer exactly must refuse it rather than emit
  approximate canonical bytes.
- Strings are emitted as raw UTF-8: `"` and `\` are
  backslash-escaped; backspace, form feed, newline, carriage
  return and tab use their short escapes (`\b`, `\f`, `\n`,
  `\r`, `\t`); control characters without a short escape are
  escaped as `\uXXXX` with lowercase hex digits; ALL other
  characters — including ALL non-ASCII characters — are
  emitted literally as UTF-8. (The golden vectors include a
  non-ASCII checkpoint name so this rule is exercised, not
  just stated.) ERRATUM (2026-11-03, spec 0.6 erratum 1):
  this paragraph previously prescribed the ASCII-safe
  `\uXXXX` form for all non-ASCII characters. That reading
  was never implemented: the golden vectors and all three
  implementations (Python, TypeScript, Rust) have always
  used the raw-UTF-8 form stated here — the café-☃ vector
  recomputes only under it. The correction is to the prose
  only; no canonical byte ever changed, so the spec seal
  and every recorded hash stand.
- The hash of a structure is the lowercase hex SHA-256 of its
  canonical bytes.

## 2. The log

The log is an append-only sequence of entries. State is a fold of
the log; the log is never rewritten.

Entry: `{"seq": int, "prev": hex64, "kind": str, "body": object,
"spec": "jacquard/0.6"}`. The entry hash is the hash of the entry.
`prev` is the previous entry hash; the genesis entry has
`prev` = 64 zero characters. `seq` starts at 0 and increments by 1.

Entry kinds: `proposal`, `decision`, `definition`, `execution`,
`sense`, `checkpoint`, `machine`, `transition`, `budget`, `price`,
`rule`, `import`, `seal`. The entry hash is the hash (section 1) of the
entry object WITHOUT the hash field itself: exactly
`{"seq", "prev", "kind", "body", "spec"}`. The golden vectors
record entries as `{"seq", "kind", "body", "hash"}`; `prev` and
`spec` are reconstructed from this section when rebuilding them.
The log's writer refuses kinds outside the list above; a fold
ignores any entry whose kind it does not know (a conforming log
never contains one). A checkpoint body is `{"name": str,
"state_hash": hex64}` where state_hash is the hash of the folded
state at that point.

Folded state:
- `units`: committed key/value state, changed only by applied
  `write` effects recorded in `execution` entries.
- `dictionary`: definitions, by name, as a list of versions.
- `decision_queue`: proposals whose decision outcome was `queued`,
  by proposal id, until an operator decision releases, rejects or
  expires them. The value stored per id is the full body of the
  `decision` entry that queued it.
- `senses`: latest published reading per sense name.
- `machines`: machine definitions, by name, as a list of versions
  (section 10).
- `machine_instances`: the current state of every machine instance,
  moved only by `transition` entries (section 10).
- `budgets`: per-producer account balance in the single accounting
  unit, from `budget` grants minus the priced cost of applied
  `spend` effects in `execution` entries (section 11).
- `prices`: the posted price per resource, from `price` entries
  (section 11).
- `rules`: standing rules by id (section 12). A rule's stage is not
  stored here; it is the state of the rule's standing-rule machine
  instance.

The state hash is the section-1 canonical hash of an object with
exactly these nine keys — `units`, `senses`, `dictionary`,
`decision_queue`, `machines`, `machine_instances`, `budgets`,
`prices`, `rules` — each folded exactly as its section describes.
The `dictionary` and `machines` values are lists of wrappers
`{"entry_seq", "entry_hash", "definition"}`, where `definition`
holds the stored form (a stored definition, section 5, or a
stored machine, section 10).


### 2.1 Entry body schemas and folded representations

Fold-critical field names, per entry kind. Fields marked
optional may be absent; a fold uses only the fields named here.

- `proposal`: reserved; the reference kernel records proposals
  as decisions and executions, and a fold ignores proposal
  entries.
- `decision`: `{"producer", "class", "proposal_id",
  "policy_version", "outcome", "reasons", "effects"}` with
  outcome one of `allow`, `deny`, `queued`, `refused`,
  `expired`. The stored literal for a queueing decision is
  `queued`. Optional: `fault` (with outcome `refused`),
  `requests` / `irreversible` / `uses` (on `queued` decisions:
  the stored work), `wait` / `wait_refusal_at` (on `queued`
  decisions: the conditional-start spec and its refusal
  marker, section 7.1), `releases` / `rejects` / `expires` plus
  `released_by` / `rejected_by` / `expired_by` (on the decision
  that closes a queue item), `decided_by` and `policy_outcome`
  (section 12). Fold: a `queued` body enters the decision queue
  under its `proposal_id`, value = the full body; a body
  carrying `releases`, `rejects` or `expires` removes that id.
- `definition`: `{"producer", "definition"}`; the folded value
  per name is the list of `{"entry_seq", "entry_hash",
  "definition"}` wrappers (section 2).
- `execution`: `{"producer", "class", "proposal_id", "applied",
  "uses"}`; `applied` items are `{"verb", "args"}` plus optional
  `outputs`. Fold: `write` items set units, `spend` items charge
  the producer's budget (section 11.2).
- `sense`: `{"producer", "name", "value"}`; the folded reading
  for a name is the body's `value`, verbatim.
- `checkpoint`: `{"name", "state_hash"}`; no fold effect.
- `machine`: `{"producer", "machine"}`; folded like definitions,
  wrapper key `definition` holding the stored machine form
  (section 10.1, plus `action_effects`).
- `transition`: the section 10.3 fields. Fold: the value per
  instance is the OBJECT `{"machine", "state"}`, moved to the
  entry's `to` on outcomes `created` and `taken` only.
- `budget`: `{"producer", "delta"}` (optional `by`, and for
  purchases `reason`, `flow`, `extra`, `resource` — evidence
  only). Fold: the producer's key is created by its first budget
  entry or first applied spend, and `delta` is added.
- `price`: `{"resource", "price"}` (optional `by`). Fold: the
  folded price of a resource is the latest entry's price.
- `rule`: `{"producer", "rule"}`; the folded value per rule id
  is the `rule` object itself (section 12), not the whole body.
- `import`: `{"producer", "bundle_hash", "format",
  "exported_from"}`; NO fold effect. Imported configuration is
  applied by a separate `execution` entry (section 14).
- `seal`: `{"producer", "seals"}`; NO fold effect. A seal
  commits, in the log itself, to the redaction of designated
  fields in a later export (section 16). The folded state and
  the state hash are exactly as if the entry were absent; the
  entry's force is entirely in export verification.

## 3. Envelopes and verdicts

Producers submit envelopes:
`{"v": 1, "id": str, "producer": str, "kind": str, "body": object,
"declared_effects": [str], "spec_seal": hex64}`.
`id` is an idempotency key: resubmitting the same envelope returns
the original verdict and appends nothing (section 3.1 states the
rule precisely). `spec_seal` is the hash
of the raw UTF-8 bytes of the string `jacquard-spec/0.7` (not of its canonical JSON form). The envelope id used in the log
is the hash of the envelope.

Envelope kinds: `proposal` (body: `{"requests": [request]}`,
plus optional `class`, `uses`, and the conditional-start
field `wait`, section 7.1),
`definition` (body: a definition, section 5), and `machine`
(body: `{"text": <machine definition text>}`, section 10).
Validation, in order: the envelope must be an object carrying
all seven fields (else FIELD); `v` must equal 1 (else SPEC);
`spec_seal` must equal the seal (else SPEC); `kind` must be one
of the three kinds (else FIELD); `declared_effects` must be a
list (else FIELD). Extra keys are permitted and ARE covered by
the envelope id (the id hashes the whole envelope object).

A request is `{"verb": <Tier-E verb>, "args": [value...]}` plus an
optional `"irreversible": true` flag on the request.

The sequencer answers every submission with a verdict:
`{"status": "accepted" | "decided" | "REFUSED", ...}`. A refusal
carries a `name` from the refusal vocabulary and a human-readable
`detail`. Refusal names: FIELD, SEQ, PREV, HASH, SPEC,
CONSERVATION, FRAGMENT, CLASS, PROVENANCE, UNDERDECLARED, EXAMPLE
(a definition whose examples fail; added in 0.2 — in 0.1 the name
was used but not listed), and (for machine definitions)
UNREACHABLE, DEAD, AMBIGUOUS, NON_TOTAL. Every refusal of a proposal
that reaches the decision stage is itself recorded in the log as a
`decision` entry (the UNDERDECLARED refusal has been recorded since
0.1; the define-check refusal joins it in 0.7, section 3.1).
Refusals issued before any recording — envelope validation, the
request-shape check, the wait-spec checks — append nothing; section
3.1 states what resubmission means for them.

### 3.1 Resubmission (added in 0.7)

An envelope's identity is its hash: the whole envelope object,
including its `id`, its producer and its seal, is what the hash
covers (section 3). Two envelopes that differ in any field are
different envelopes, however similar their bodies.

**The recorded-verdict rule.** Once a submission is recorded in
the log, resubmitting the same envelope returns the recorded
verdict and does nothing else: it never re-decides, never
re-executes, never re-queues, and never appends an entry. The
returned verdict is the verdict of the submission, with one
field added — `"duplicate": true` — so a caller can tell a
replay from a fresh decision. The check is made against the
log, not against process memory: a sequencer constructed over
an existing log rebuilds the recorded verdicts from the log's
entries at construction, so the rule holds across processes
and across checkpoint entries (a checkpoint is an entry like
any other; it neither truncates nor resets the record). In
0.6 and earlier the rule was honoured only inside one process
(the verdict cache was per-process), so a fresh-process
duplicate was re-decided: an allowed duplicate silently
re-executed, a queued duplicate appended a second decision
entry and raised an unhandled refusal from machine-instance
creation, and a refused duplicate appended a second refusal.
0.7 makes the 0.6 text's promise true at kernel level.

What counts as recorded, per kind:

- A **proposal** is recorded by its submission decision: the
  first `decision` entry carrying its proposal id that is not
  an operator release/reject/expire entry and not a
  wait-pump record. Its recorded verdict is reconstructed
  from that entry — outcome `allow`/`deny`/`queued` map to
  the verdict outcomes `allow`/`deny`/`queue`, with the
  entry's reasons; an outcome of `refused` with a `fault`
  reconstructs the REFUSED verdict of that name, with the
  recorded detail. Later entries about the same proposal
  (operator decisions, wait-pump records, executions) do not
  alter the recorded verdict.
- A **definition** or **machine** is recorded by its
  acceptance entry. From 0.7 those entries carry the
  envelope hash in an `envelope` body field, and the
  recorded verdict is the acceptance verdict (its `entry`
  is the acceptance entry's own hash). Acceptance entries
  written before 0.7 do not carry the field, so replay of
  definitions and machines is a 0.7-forward guarantee;
  proposal replay covers every log ever written, since
  decision entries have always carried the proposal id.
  Recording the envelope hash in the acceptance entry has
  one visible consequence, stated rather than hidden: the
  entry hash commits to the submitting envelope, so the
  folded dictionary and machine sections (which identify
  versions by entry) make a log's state hash a fact about
  that log's own submission history. State hashes were
  already history-dependent (versions carry entry sequence
  numbers); they are per-log facts, and no rule in this
  specification equates the state hashes of two different
  logs.

**Later operator decisions do not change the recorded
verdict.** If a queued proposal has since been released,
rejected or expired by the operator, resubmitting its
envelope still returns the submission verdict (`queue`),
marked as a duplicate. A verdict is a fact about a
submission event, and the log's facts do not change; the
item's current disposition is read from the record (the
decision queue and status surfaces), not from a
resubmission. The alternative — returning the item's
current disposition — was weighed and rejected: it makes
one question receive different answers at different times,
and it attributes a later decider's decision to the
original submission.

**A named refusal for duplicates was also weighed and
rejected.** Duplicate delivery is the normal shape of
cross-process submitters — the shipped adapters are fresh
processes per call and deliver at-least-once — so a refusal
would push idempotency into every adapter and present an
error surface for a benign replay. The recorded verdict is
the answer a retrying submitter needs: what was decided,
once.

**Pre-recording refusals.** A submission refused before
any recording (envelope validation in the order stated
above, the request-shape check, the wait-spec checks of
section 7.1) appends nothing and executes nothing.
Resubmitting it re-derives the refusal from the envelope
and the current dictionary; the observable invariants of
the recorded-verdict rule — no second decision, no second
execution, no second queue entry — hold trivially. One
refusal moved across the line in 0.7: a proposal whose
embedded definition fails its check previously recorded
nothing but lifecycle steps; it now records a fault
`decision` entry exactly as the UNDERDECLARED refusal
does, so every proposal that reaches the decision stage
has exactly one submission decision and its verdict is
replayable under the rule.

**Across spec versions.** The rule applies to envelopes
sealed under the running spec version. An envelope sealed
under an earlier version is refused on its seal, like any
foreign-version envelope; its recorded verdict remains
readable from the log it was decided in. Logs written
under earlier versions fold unchanged under 0.7.

## 4. Effects

The effect vocabulary is the set of Tier-E verbs (section 6) plus
the class markers `reads` and `irreversible`.

- A raw proposal's actual effects are derived from its request
  list: the set of verbs named, plus `irreversible` if any request
  carries the flag. If `declared_effects` does not cover the actual
  effects, the submission is REFUSED(UNDERDECLARED) and the refusal
  counts as a fault on the producer's record.
- A definition's effects are **computed** (section 5), never
  taken from the author. A definition that carries a
  `declared_effects` field not equal to the computed set is
  REFUSED(UNDERDECLARED).
- The computation is complete over the definition's expansion
  (criterion C2): a word's computed effects are the union of
  the Tier-E verbs at every token position in its body —
  including positions inside any nested token form — and,
  recursively, in the bodies of every word it references.
  There is no token position whose contents escape accounting:
  the only value a body can hold without accounting is a
  literal's value, and a literal's value is data — it is never
  evaluated as a body, by this or any composition of words,
  since the language has no form that evaluates data as code.
  A form that quotes a body for later evaluation, if a future
  version defines one, has its quoted body accounted at
  definition time like any other token position: quotation
  defers evaluation, never accounting. (Added in 0.4, closing
  the hazard recorded in
  docs/completeness-probes-2026-11-02.md: a Tier-E verb inside
  an experimental `{"any": [...]}` quotation computed
  effect-free under the pre-0.4 walk.)

## 5. Definitions and the dictionary

A definition:
`{"name": str, "signature": {"ins": [type], "outs": [type]},
"body": [token], "examples": [example], "declared_effects":
optional [str]}`.

Types: `val`, `int`, `bool`, `str`, `list`, `map`.

Body tokens:
- `{"lit": value}` pushes a literal.
- a string names a primitive, a previously defined word, or a
  syntax form.
- `{"if": [token], "else": [token]}` evaluates the then-branch if
  the top of stack is true, else the else-branch (empty if absent).
  Both branches must leave the stack in the same shape.

These are the only token forms. A dict token of any other form
is REFUSED(SPEC) at definition time, with the form's key named
in `detail` — an implementation must not accept a form it does
not account, and must not fail one incidentally under another
refusal name. The effects walk that computes a definition's
effects (section 4) descends into every token position of
every form — both branches of an `if`, and the body of any
form a future version may add — except inside a `{"lit": ...}`
value, which is data and contains no token positions.

Syntax forms (evaluator-level; they manipulate only values on the
evaluation stack, grant no access to state or effects, and are not
primitives): `dup`, `drop`, `swap`, `over`, `snoc` (append to a
list), `assoc` (set a key in a map), `getf` (read a key from a
map), `first` (first element of a list), `cat` (concatenate two
strings).

Semantics:
- Definitions may only reference primitives and words that already
  exist. The reference graph is therefore acyclic, and expansion
  always terminates.
- At definition time the kernel checks: the signature against the
  body (a typed stack simulation); the computed effects; and every
  example. An example is `{"args": [value], "state": {"units":
  {...}, "senses": {...}}, "expect": [value], "requests": [verb]}`
  (state, expect, requests optional; defaults empty). The example
  is evaluated against the given state; the final stack must equal
  `expect`, and the emitted request verbs must equal `requests`
  when given. Any failure refuses the definition with the check
  named in `detail`.
- A definition is stored as a `definition` entry. Its stored form
  records, for every word it references, the referenced version's
  entry hash (`refs`). Evaluation resolves references by those
  hashes, so redefining a word never changes what an existing
  definition does. Redefinition appends a new version; the name
  resolves to the latest version for new definitions.
- Evaluating a word never executes an effect. Tier-E tokens append
  a request to the evaluation's request list. Only the kernel
  executes requests, after a policy decision (section 7), and a
  proposal's full request list is applied atomically or not at all.

## 6. Primitives (26)

Words are evaluated by the kernel. Tier-P primitives are pure: they
read state views and return values. Tier-E verbs are effects: they
may be named in a definition body or a proposal request list, and
are executed only by the kernel.

Tier P (18):
| # | name | signature (ins -> outs) | meaning |
|---|---|---|---|
| P1 | self | -> str | id of the evaluating context |
| P2 | now | -> int | sequencer logical clock (entry count) |
| P3 | get | str -> val | committed unit read (null if absent) |
| P4 | keys | str -> list | committed unit names with prefix, sorted |
| P5 | cands | str -> list | tentative candidates for a unit |
| P6 | age | int -> int | staleness of an entry seq, in entries |
| P7 | record | str str -> map | producer record for (producer, class) |
| P8 | sense | str -> val | latest sense reading (null if absent) |
| P9 | similar | str int -> list | recorded proposal ids of a shape |
| P10 | history | str int -> list | recent values/decisions for a unit |
| P11 | eq, lt, gt | val val -> bool | comparisons |
| P12 | and, or, not | bool.. -> bool | boolean core |
| P13 | add, sub, mul, div, mod | int int -> int | integer arithmetic (div/mod by zero refuse) |
| P14 | neg, abs, min2, max2 | int -> int / int int -> int | unary/pair arithmetic |
| P15 | count, sum, min, max, contains | list.. -> .. | list aggregations |
| P16 | hash, verify | val -> str / val str -> bool | seal arithmetic |
| P17 | evidence | int -> list | evidence refs on a log entry (by seq) |
| P18 | def | str -> map | a definition's stored form (introspection) |

Tier E (8):
| # | name | arguments | effect |
|---|---|---|---|
| E1 | write | unit (str), value | writes committed state |
| E2 | dispatch | action (map) | hands an action to an executor |
| E3 | spend | resource (str), amount (int) | spends from a budget |
| E4 | notify | surface (str), artifact | notifies an operator surface |
| E5 | send | channel (str), payload | sends to a third party |
| E6 | schedule | at (int), proposal (map) | schedules a future proposal |
| E7 | define | definition (map) | submits a definition |
| E8 | checkpoint | name (str) | writes a checkpoint |

Not primitives: model invocation (an executor step; its output
re-enters as proposals), network I/O (behind dispatch/send
adapters), similarity training (offline; `similar` is read-only).

## 7. Policy gate

The policy is a pure, versioned function:
`(producer, kind, effects, record) -> allow | deny(reason) |
queue`. This version is `policy/1`:

1. If the producer's standing is `suspended`, deny.
2. Effects containing any of `send`, `notify`, `spend`, or the
   `irreversible` marker require an operator decision, unless the
   producer is `operator`: outcome `queue`. The proposal is placed
   in the decision queue (batched for the operator) and processing
   of everything else continues; queueing never blocks a submission.
3. Otherwise allow.

Allowed proposals are executed by the kernel executor and recorded
as `execution` entries. Denied and queued outcomes are recorded as
`decision` entries. An operator releases a queued proposal by
submitting a decision referencing its id; the release executes the
original request list atomically. An operator may instead reject a
queued proposal (decision with outcome `deny` and `rejects` set to
the proposal id) or expire it (outcome `expired`, `expires` set);
both close the queue item without executing it. A closing
decision's reasons default to `released-by-operator`,
`rejected-by-operator` or `expired-in-queue`; a caller may
supply a single reason instead, which replaces the default
on the decision entry (the wait pump's `wait-expired:<guard>`
and the booking profile's `preempted-by:<id>`, sections 7.1
and 11.4, arrive this way -- the decision entry is written by
the closing functions, so a reason a caller needs on the
entry can only arrive through them).

### 7.1 Conditional starts: the `wait` field

A proposal body may carry one extra field:
`wait: {"guard": <word name>, "deadline_seq": <int>}` --
"starts when X lands", carried as data on the proposal
itself, so the waiting exists in the record: it can be
listed, expired, and audited. The guard is an ordinary pure
dictionary word over committed state. The semantics are
state-based, not edge-based: the guard reads current
committed state at re-evaluation time, so a landing that was
retracted by compensation before re-evaluation does not
start the waiter; a later re-landing does.

Shape and validation. All of this happens BEFORE anything
is appended; every refusal in this paragraph appends nothing
and is returned as a REFUSED verdict (request-shape refusals
under section 3 are checked first). A `wait` that is not an
object with a string `guard` and an integer `deadline_seq`
(booleans are not integers) is refused FIELD. A guard that
does not resolve to a dictionary word is refused SPEC; a
guard whose signature is not (map -> bool) is refused FIELD;
a guard with non-empty computed effects is refused SPEC.
The underdeclared check is also made here, before queueing:
the envelope's declared effects must cover the proposal's
actual effects (its request verbs, plus the `irreversible`
marker when the body carries it), else the submission is
refused UNDERDECLARED and appends nothing. (The normal
path's underdeclared refusal appends a fault decision; a
queued waiter never reaches that path's check, so the check
is made pre-append here -- queueing an underdeclared
proposal would be worse.)

Submission-time evaluation. The guard is then evaluated at
once, with payload `{"proposal_id": <envelope id>}`. A
Refusal raised by the evaluation is a submission refusal:
the verdict carries that refusal's name and nothing is
appended -- fail fast while the producer is present. A pure
guard cannot emit requests; if evaluation nevertheless
emits any, the submission is refused SPEC. A guard leaving
anything other than exactly `[true]` or `[false]` is
refused FIELD.

- Guard true at submission: the proposal takes the normal
  path, and `wait-satisfied:<guard>` is prepended to the
  decision's reasons, whatever the outcome.
- Guard false at submission: the proposal is queued. The
  decision entry is exactly the stored form of an ordinary
  queueing decision (requests, irreversible, uses, effects)
  PLUS `"wait": <the wait spec>`, with outcome `queued` and
  reasons `["waiting:<guard>"]`; the proposal lifecycle
  steps submit then hold; NO approval instance is created
  (waiters are not approval items); the verdict outcome is
  `queue`. No new fold section exists: the fold stores whole
  decision bodies in the decision queue, so the nested wait
  spec survives a refold intact.

The pump. After any public sequencer operation that appended
entries -- submit, release_queued, reject_queued,
expire_queued, grant_budget, post_price, buy_weight,
submit_sense, checkpoint -- the sequencer re-evaluates
outstanding wait guards before that operation returns.
(Machine-step methods are exempt: every flow path that steps
a machine also submits proposals, which pump.) The pump's
own appends never re-enter it. Ordering rules:

- Post-fold evaluation: the pump runs after the triggering
  entries are folded, against the resulting committed state
  -- a guard never reads a half-applied commit.
- Fixpoint: the pump makes passes over a snapshot of the
  decision queue, in queue order, until a pass changes
  nothing, at most 64 passes. A waiter's execution may write
  the unit another waiter's guard reads; such cascades
  complete within the one triggering call.
- Guard-true beats deadline: the guard is checked before
  the deadline at the same log position. Expiry exists to
  bound waiting for a condition that does not hold, so a
  condition that holds in current state releases even past
  its deadline.
- A refusing guard is treated as not-true for that pass and
  is recorded, never swallowed and never fatal to the
  unrelated submission that triggered the pump: the pump
  appends a re-queueing decision entry for the waiter --
  outcome `queued`, reasons
  `["wait-guard-refused:<refusal name>"]`, all stored fields
  preserved including `wait`, plus `wait_refusal_at`: the
  sequence number of that record itself. Re-recording is
  skipped while that record is still the last entry in the
  log (nothing has changed since it was recorded). A
  recorded refusal counts as a change for the fixpoint, but
  the skip rule bounds re-recording. Expiry (below) is
  evaluated on passes where the guard returns false.
- Deadline: `deadline_seq` is an absolute log position, and
  queueing's own entries count toward it (queueing a waiter
  appends its decision and lifecycle entries). When the log
  length exceeds `deadline_seq` and the guard is false, the
  waiter is expired through the ordinary expire path with
  reason `wait-expired:<guard>`.
- Supersession: the queueing decision records the wait; the
  decision that fires, rejects or expires the waiter
  supersedes it for disposition. Record scoring (section 8)
  treats the first decision per proposal as primary and
  release decisions as follow-ups.

Composition with policy. A fired guard re-decides the
proposal through the ordinary policy decision, fresh --
policy gate plus the standing-rule hook, with bookkeeping
as in the normal path -- and never bypasses it. The fired
decision's reasons are `["wait-satisfied:<guard>"]` plus
the fresh decision's reasons. Outcomes: allow -> a decision
carrying `releases` (the fold pops the queue entry),
lifecycle decide, the stored requests executed, commit and
close; deny -> a decision also carrying `releases`,
lifecycle refuse; queue -> an ordinary approval-queue entry
(a fresh queueing decision with the stored fields and NO
`wait` -- the wait is spent -- and an approval instance
created as the normal queue path does).

## 8. Producer records

Records are a projection of the log, per (producer, class):
submissions, allowed, denied, queued, faults (UNDERDECLARED
refusals), executions; and per producer acting as a standing rule:
outputs produced and outputs later referenced by a use entry.
Records are computed from the fold, never stored as truth.

## 9. Golden vectors

`spec/vectors/` holds worked structures with their canonical bytes
and hashes: entries in a short chain, an envelope and its id, a
definition and its computed effects, a folded state and its
checkpoint hash. An implementation that reproduces every vector
implements sections 1-5 compatibly. The vectors also carry a
`senses` section (section 11.3): for the contention and
authority senses, cases built from stated entry lists (mini
logs), each `{"entries", "subject", "expect"}` where expect is
`{"value", "method", "as_of_seq"}`, verified by folding the
entries and recomputing the sense at the subject. Sense
computation is kernel work over the log, not fold work: the
TypeScript conformance checker declares this section SKIP
(conformance/ts/GAPS.md). The vectors also carry an `anchor`
section (section 15): one checkpoint for the vector entry chain,
issued under a published test key recorded in the vectors, with
its envelope and signature; signature verification is verifier
work, not fold work, and the TypeScript checker likewise
declares it SKIP.

## 10. Machines

Behaviour with a lifecycle — proposals, actions, standing rules,
workers — is a *machine*: a flat state machine defined in a
restricted text format, checked statically at definition time,
whose every step is written to the log.

A machine definition is submitted as a `machine` envelope whose
body is `{"text": <definition text>}`. An accepted machine is
appended as a `machine` entry whose body is `{"producer", "machine"}`
where the stored machine is the parsed form below plus
`action_effects` (the union of its action words' computed effects).

### 10.1 Definition text

One directive per line; `#` starts a comment; blank lines are
ignored.

- `machine <name>` — first directive, exactly once.
- `initial: <state>`
- `terminal: <state>, ...` or `terminal: none`
- `events: <event>, ...` — the declared event alphabet.
- `state <name>` — optional explicit state declaration.
- `<from> -> <to> : <event>` — a transition; optionally followed
  by `[<guard-word>]`, by `/ <action-word>`, and/or the keyword
  `otherwise` (the fallback for that (state, event) pair when no
  guarded transition fires).
- `ignore <event> in <state>, ...` or `ignore <event> in *` —
  the event is explicitly a no-op in those states; `*` means
  every state that has no transition for the event.

States are all names appearing as initial, terminal, declared,
transition endpoints, or explicit ignore targets. The parsed
(stored) form is `{"name", "initial", "terminals", "events",
"states" (sorted), "transitions", "ignores", "source_hash"}`;
each transition is `{"from", "event", "to", "guard", "action",
"otherwise"}` with absent guard/action as null.

### 10.2 Static checks

Checks run in a fixed order and refuse by name:

1. FIELD — malformed text; a duplicate transition; an event used
   but not declared in the alphabet; a terminal that is not a
   state; a (state, event) pair that is both transitioned and
   explicitly ignored; a guard word whose signature is not
   (map -> bool); an action word that does not take the payload
   map as its single input.
2. SPEC — a guard or action word that does not resolve to a
   dictionary word; a guard word with non-empty computed effects
   (guards are pure by construction: effects are computed, so a
   guard that could emit an effect request is refused, not
   trusted).
3. UNREACHABLE — a state no path from the initial state reaches.
4. DEAD — a non-terminal state with no outgoing transitions, or,
   when terminals are declared, a state from which no terminal
   state is reachable. (Terminal states need no outgoing
   transitions; `terminal: none` machines exempt the reachability
   half.)
5. AMBIGUOUS — for one (state, event): more than one guarded
   transition, more than one `otherwise` fallback, a plain
   unguarded transition competing with a guarded or fallback
   transition, or more than one plain transition. Guard
   disjointness cannot be proven statically, so at most one
   guarded transition plus one `otherwise` fallback may share a
   (state, event) pair.
6. NON_TOTAL — a (state, event) pair, over all states and the
   declared alphabet, that neither transitions nor is explicitly
   ignored.

### 10.3 Instances and the transition hook

An instance is created by a `transition` entry with event
`@create`, `from` null, `to` the initial state, outcome `created`.
Each subsequent step appends a `transition` entry: `{"producer",
"machine", "instance", "event", "from", "to", "guard", "action",
"requests", "outcome"}`. Firing, for a (state, event) — the
AMBIGUOUS check guarantees the shapes never compete: if a plain
transition exists it fires. If a guarded transition exists, its
guard word is evaluated against the event payload map and it
fires iff the evaluation's result stack is exactly the
one-element list `[true]`; if the guard leaves `[false]`, the
`otherwise` fallback fires when present. Outcomes:
`taken` (state moves to `to`; the action word, if any, is
evaluated against the payload and the requests it emits are
recorded on the entry — executing them is the caller's work, the
machine only records), `ignored` (an explicit ignore: state
unchanged), `no-transition` (only guarded transitions whose
guards all returned false: state unchanged). Folding: an
instance's state is the `to` of its latest `created`/`taken`
transition entry.

### 10.4 The lifecycle machines

Seven machines ship as profile definitions in the reference
implementation (`src/jacquard/lifecycles.py`) and are submitted
like any other machine definition: proposal, action,
standing-rule, producer-standing, commit-batch, approval, worker
(state graphs as in the design record). A kernel with them
installed runs its lifecycles through the machines:

- each proposal gets a proposal-machine instance whose id is the
  envelope id: received -submit-> validated; the gate's outcomes
  step hold (queued), decide (allowed) or refuse (denied,
  underdeclared, or carrying an invalid definition); an allowed
  proposal steps commit then close; a released queued proposal
  steps decide (from tentative), commit, close.
- each dispatched request in an executed proposal gets an
  action-machine instance `<proposal-id>/action-<index>`, stepped
  approve then dispatch at execution time; executors report
  confirm, fail, compensate (or reject) against the same id —
  the id is the action's idempotency key.
- each queued proposal gets an approval-machine instance
  `approval:<proposal-id>`: created pending; releasing steps
  present then approve; rejecting steps present then deny;
  expiring steps expire. Rejection and expiry are decision entries
  carrying `rejects` / `expires`, and close the queue item exactly
  as `releases` does.
- producer standing may be driven through the producer-standing
  machine (`transition_standing`), whose current state is what
  the policy gate reads.

A kernel without the lifecycle machines installed behaves exactly
as the 0.1 kernel: lifecycle stepping is active only for machines
present in the kernel's registry.

## 11. Scheduling, budgets, senses

### 11.1 Fair scheduling

Admission to the sequencer, executor slots, and attention in
the decision queue are one mechanism: weighted fair queueing
over flows. A flow is a (producer, service class) pair. Every
flow has baseline weight 1. An item arriving at virtual time v
for a flow whose last finish tag is f receives start tag
max(v, f) and finish tag start + size / weight, with weight the
flow's weight at arrival; the scheduler serves the smallest
finish tag, ties by arrival order. Virtual time is the start
tag of the most recently served item (0 before any service).

Extra weight is purchased from the producer's budget (11.2) at
the posted price of a resource per unit of extra weight. A
purchase is recorded as a `budget` entry with reason
`weight-purchase` (the evidence) and takes effect at the
virtual time of purchase; its contribution decays, halving
every HALF_LIFE virtual-time units (reference default 1000),
back to baseline — a purchase buys a temporary share, never a
permanent one. Aging is a secondary guarantee: an item whose
wait exceeds AGING_THRESHOLD virtual-time units (reference
default 50) has its finish tag reduced by (wait − threshold) ×
AGING_RATE (reference default 0.01). The guarantees are:
baseline weight always earns its share (no starvation), and no
flow exceeds its purchased share by more than tag slack (no
capture).

### 11.2 Budgets and prices

One accounting unit for everything. `budget` entries grant
(`delta` > 0) or record purchases (`delta` < 0); `price` entries
post the price of a resource. The folded balance of a producer
is the sum of its grants minus, for each applied `spend` effect
in its `execution` entries, amount × the price in force at that
point in the log (the latest `price` entry for the resource
before it; default price 1 when never posted). Exhaustion
degrades, never blocks and never borrows: a purchase the
balance cannot cover is refused CONSERVATION, and spending
authority itself remains a policy matter (section 7).

### 11.3 Senses

A sense is a read-only projection of the log and folded state,
published as a `sense` entry (body `{"producer", "name",
"value"}`; the fold stores the body's `value` verbatim). For
senses published by the senses framework the value is the
reading object `{"value", "method", "as_of_seq"}`: the reading,
how it was derived, and the log position it describes. A sense
entry may also carry a bare value (a boolean, a number) when
published directly; the fold does not distinguish the two. Sense values use canonical types only;
rates are integer basis points. Computing a sense appends
nothing. Built-in senses: `queue-depth` (folded queue size),
`output-use:<producer>` (the records projection as a reading:
outputs, used, ratio in basis points), `starvation` (per-flow
waiting/served/weight evidence from a live scheduler's
counters), `calibration-drift` (a stub — kernel-wide allow-rate
drift between fixed windows; per-rule calibration is section
12's business, and the stub's method says so), and the two
domain senses specified in full below: `contention` and
`authority` (both added in 0.3).

Published-value determinism (all senses, stated precisely
because two different claims are easily conflated): readings
are *published values*. Refold reproduces state from the log
-- the same log folds to the same state, published readings
included. A reading is additionally a pure function of the
entry prefix up to its `as_of_seq` plus its parameters, so
recomputation at that position reproduces the reading
byte-identically. Computing a sense appends nothing;
publication is a separate sense entry.

**The contention sense.** Name: `contention:<subject>`,
where the subject grammar is
`<box>/<seat>/<start>/<end>/<producer>/<id>` -- the
candidate's box, seat, start and end (integer minutes),
producer and booking id -- parsed from the right into six
fields, so the box field itself may contain `/` when a name
is parsed. (Constructing a name is stricter: the booking
profile, section 11.4, refuses any of box, seat, producer
or id containing `/` with FIELD, rather than misparse
silently.) Read set: committed units with prefix
`booking/<box>/`. A committed booking contends if and only
if ALL of these filters pass: its status is `"active"`
only (done, cancelled, preempted and expired bookings are
inert); its id differs from the candidate's id (a booking
never contends with itself -- a committed row whose id
equals the candidate's id is excluded even when its
producer differs); its producer differs from the
candidate's producer (a same-producer overlap is a renewal,
not contention); its check-by is null or >= the candidate
start (a booking whose check-by passed before the candidate
starts is dead); the seat rules -- equal seats contend if
and only if the seat is in the exclusive set {zcode, mcode,
claude-code, gpu, stage, kimi, box}, `"box"` contends with
every seat, and other distinct seats do not contend; and
strict interval overlap, candidate.start < other.end and
other.start < candidate.end (touching endpoints do not
contend). The value is `{"contenders": [...], "count": n,
"max_rank": r, "top_id": id-or-null, "unclassified": [...]}`:
contenders are objects `{"id", "producer", "seat",
"start", "end", "rank"}` sorted by id; max_rank is the
highest contender rank, -1 when there are none; top_id is
the highest-rank contender's id (ties: smallest id), null
when there are none; unclassified is the sorted list of
seat strings -- the candidate's seat and the seats of
status-"active" rows under the prefix -- that are in
neither the exclusive set nor {"detached"}. Rank otherwise
plays no part in contention itself. The reading's method
string states the read set, every filter, and the
unclassified rule. Publication in the booking flow is at
decision time (the reading's as_of_seq is the decision's
own position), never as a separate operator action, and is
unconditional on the decision's outcome -- a denied booking
still leaves its reading in the record as an audit artifact.
Readings never feed the sense's own read set, so they
cannot compound.

**The authority sense.** Name: `authority:<producer>`; the
subject is the producer whose grant ceiling is read. Read
set: log entries passing three filters -- the entry kind is
`execution`; the entry body's producer is `"operator"`;
and the entry's applied writes include a write to unit
`authority/<producer>`. Among the writes passing all three
filters, the LATEST wins: its written value is the ceiling,
so a later lower grant is a downward revocation; `grants`
is the count of such writes. The value is `{"ceiling":
<value or null>, "grants": n}`; with no operator grant the
ceiling is null and grants 0. Provenance comes from the
log, not from the unit's current holder: under policy/1 any
producer may write any unit, so a producer's own write to
`authority/<self>` may land in committed state -- and fails
the producer filter here, so it is visible in the log and
inert. The unit's current value alone is NOT evidence of a
grant; this sense is the only sanctioned reading of
`authority/` units.

### 11.4 The booking application profile

The booking board's rules ship as definitions, not kernel
code: the two senses above (kernel-resident, because senses
are the only mechanism for kernel-computed readings), seven
dictionary words, one lifecycle machine, and a flow module
that routes between them. The profile computes no overlap
and no rank comparison outside the kernel: the senses
compute, the words turn published readings into guard
booleans and the effective rank, and the machine's guards
decide transitions.

Record schema. A booking record, stored at unit
`booking/<box>/<id>`, is `{"id", "box", "producer",
"seat", "start", "end", "checkby", "status", "rank",
"asserted_rank"}`. `rank` is the EFFECTIVE rank: the
asserted rank clamped to the granted ceiling,
`min(asserted, ceiling)`, and 0 with no grant.
`asserted_rank` is kept beside it, so the record never
launders a claim into a fact.

Grants. A grant is an operator proposal (class `config`)
writing `authority/<producer>` = ceiling. Grants are
recognised only through the authority sense (11.3): the
unit value alone is not evidence, and the profile's words
consume the sense, never the raw unit. The words:
`booking-clear` (the reading's count is 0 AND its
unclassified list is empty), `booking-contended` (count >
0), `booking-outranks` (count > 0 and the candidate's rank
exceeds the reading's max_rank), `booking-tied` (count > 0,
rank > 0, and rank equals max_rank), `rank-granted` (a
grant exists and the asserted rank does not exceed the
ceiling), `effective-rank` (the clamp above), and
`rank-below` (rank < a stated limit).

Seats and the fail-closed guard. Seat classification is the
contention sense's table: the exclusive set {zcode, mcode,
claude-code, gpu, stage, kimi, box} plus the one classified
non-exclusive seat, `detached`. A seat in neither set is
unclassified, and `booking-clear` requires the reading's
unclassified list to be empty -- so a misspelled seat holds
the booking for a human instead of silently clearing. (The
sense itself stays faithful to the stated rules; the
fail-closed check lives in the guard, where a deployment
can amend it.) Spelling is case-exact; the kernel does no
normalisation.

The booking machine. States: requested (initial), held,
active, and terminals done, cancelled, preempted, expired.
Load-bearing transitions: requested -> active on `commit`
guarded by booking-clear; requested -> held on `commit`
otherwise; requested -> held on `tie` guarded by
booking-tied; held -> active on `commit` guarded by
booking-clear; held or active -> preempted on `preempt`;
plus cancel, complete and expire transitions as in the
machine text shipped in the profile module.

Preemption. When a candidate outranks every contender, the
flow preempts each contender with ordinary operator
proposals (class `preemption`) that write the loser's
booking record to status `"preempted"` and write a
preemption record at `preemption/<loser-id>`:
`{"winner", "winner_producer", "rank", "authority_sense",
"at_seq"}` -- the winner's id and producer, its effective
rank, the authority sense name its rank was read from, and
the log position. The loser's booking instance is stepped
`preempt`. A HELD (queued) booking disposed of by a winner
that outranks it is rejected from the decision queue with
reason `preempted-by:<winner-id>` (section 7's reason
parameter), given the same preemption record, and stepped
`preempt`; its write never executes. No kernel writes are
invented: the whole override replays from ordinary entries
through the ordinary policy gate, and an audit replay from
the log alone reconstructs who overrode whom, by whose
authority, and at what cost (the loser's lost interval, in
its preempted record).

Ties. A tie is not a refusal: the challenger is queued under
a taken `tie` transition whose guard is booking-tied; the
published contention reading names the equal-rank contender
it tied with; the incumbent is untouched. The interim
disposition is stated, not implicit: **the incumbent holds
the interval while the challenger waits** -- "no silent
winner" means no *unrecorded* winner, and the operator
queue surfaces such items as authority ties for the
operator's batched decision. Equal rank is likewise left
queued by disposal: only a strictly lower rank is disposed
of.

## 13. Decision-model providers

Deployments may plug in decision models (judgement models that
return typed probabilities or choices) behind one interface: a
provider has a name and a `judge(text, question, choices)`
operation returning a choice among the given labels and a
probability in basis points for the first label, or declining.
A provider's reading may be published only as a sense (section
11.3), with the provider named in the reading. Providers are
advisors: no allow, deny, queue, release, or lifecycle outcome
may depend on a provider's verdict, and the kernel imports no
provider-specific code — adapters live outside the kernel, and
changing providers changes which senses exist, never how
decisions are made. The record gates; the model only testifies.

## 12. The learner and standing rules

Learned behaviour enters as a *standing rule*: a candidate rule
whose lifecycle is the standing-rule machine (candidate,
evaluated, shadow, canary, active, demoted, quarantined,
revoked), every transition a log entry.

A rule is a `rule` entry: `{"rule_id", "definition", "shape",
"predicted_outcome", "support", "dominance_bp", "origin", ...}`
where shape is (producer, class, exact effect set, signature)
and definition names a pure dictionary word — the *recogniser* —
that decides whether a proposal matches the shape. The
recogniser's input is the map `{"class", "effects",
"signature"}` projected from the proposal. A rule's identity
is a hash of its shape, its prediction and its origin:
identity is derived from instances, not assigned. A rule's
stage is never stored in the rule entry; it is the state of
the rule's standing-rule machine instance, whose id is the
rule id.

### 12.1 Shape signatures

The signature refines a shape within the queued population —
the proposals the gate holds for an operator. It is a pure
function of the request list recorded on the queued decision,
so it is derivable from the log alone. For each request, in
order, the signature carries one component `[verb, detail]`:

- `dispatch`, when the request's action carries a `cmd` token
  list: the command skeleton. If the list is a shell `-c`
  invocation (the first token's basename one of `sh`, `bash`,
  `dash`, `zsh`, `ksh` and the second token `-c`), the script
  is the third token; otherwise the token list itself is the
  single segment. A script is split into segments on the
  shell operators `&&`, `||`, `;`, `|` and newlines, and
  each segment is split into tokens on whitespace (quotes
  group as in POSIX shell). Each segment contributes a list:
  the program's basename, then one entry per remaining
  token — a flag keeps its name (the part before any `=`), a
  token containing `://` becomes `<url>`, a token containing
  `/` becomes `<path>`, an all-digit token becomes `<num>`,
  and any other token (a bare word: a subcommand, a module
  name) stays literal.
- `write`: the file extension of the target unit's basename
  (from the last `.`, dot included), or empty when the
  basename carries no dot.
- `send`: the channel's host, or empty when the channel has
  none.
- Any other verb, and any request whose arguments do not
  have the stated form: empty detail.

A proposal the gate decides directly (allow or deny, never
queued) carries the empty signature `[]`: the signature
discriminates among queued items, and only queued decisions
record their request list.

### 12.2 Joined outcomes and operator labels

A queued item's story ends with a follow-up decision. The
*joined outcome* of a primary decision is:

- its own outcome, when the gate decided it directly
  (allow or deny);
- the operator's label, when it queued: a follow-up decision
  whose `releases` names the item AND carries `released_by`
  labels it *released*; a follow-up whose `rejects` names it
  AND carries `rejected_by` labels it *rejected*;
- no outcome, when it expired (whoever expired it — expiry
  is not a judgement) or is still undecided.

Re-decisions written by the wait pump carry `releases` but
no `released_by`; they are mechanics, not operator
judgements, and never label an item. And a label is honest
about its scope: a release is the operator accepting THIS
item, not a standing permission for its shape. Candidates
mined from labels enter the pipeline at offline evaluation
and climb every stage exactly as policy-mined candidates do.

### 12.3 The pipeline

1. *Mining.* Primary decisions (the first decision per
   proposal; release/reject/expire follow-ups and fault
   records are not fresh evidence) are grouped by shape over
   a training window (reference: the first 70%). Two passes
   run over the window:
   - the *policy pass* groups by the gate's primary
     outcomes, as before; its candidates carry origin
     `mined`;
   - the *operator pass* groups the joined decisions whose
     label source is the operator. Support is the count of
     LABELLED instances of the shape; a shape whose dominant
     label (reference: ≥80% of its labelled instances) is
     released yields a candidate predicting allow, and one
     dominated by rejected yields a candidate predicting
     deny. Its origin is `operator`.
   A shape below the minimum support (reference: 3) in a
   pass yields no candidate from that pass.
2. *Offline evaluation.* The candidate's prediction is
   scored against the held-out tail, under its own scoring
   basis (section 12.4). Below the bar (reference: 80%
   agreement) it stays a candidate; the scores are recorded
   on the rule entry either way.
3. *Shadow.* The rule predicts but never decides. Agreement
   with real outcomes is scored from the log.
4. *Canary, then active.* Promotion at each stage requires
   scored agreement (reference: ≥90% over ≥3 fresh samples at
   that stage). There is no faster lane for shapes carrying
   protected effects.
5. *Production scoring and demotion.* An active rule decides
   matching proposals through the sequencer's rule hook,
   within bounds: it never overrides a suspension, and it
   never turns an outcome into a queue. Matching is by
   producer, class and exact effect set; an operator-origin
   rule must ALSO match the proposal's signature, computed
   from its request list by section 12.1. Every rule-made
   decision records `decided_by` and `policy_outcome` (what
   the policy gate would have done). An active rule whose
   agreement over fresh samples collapses (reference: <50%
   over ≥5) is demoted automatically — the regress
   transition and the scores are in the log.
6. *Revocation.* One call steps the rule to revoked. The
   hook reads stage from folded state per proposal, so
   revocation takes effect on the next proposal and decides
   nothing further.

### 12.4 Scoring basis

Scoring in every stage counts, per matching primary decision
after the stage marker, agreement between the prediction and
the actual outcome — where "actual" is relative to the
rule's origin:

- A policy-origin rule: the actual outcome is the primary
  outcome, and for a rule-made decision the recorded
  `policy_outcome` — the rule is compared against the
  constitution, never against itself.
- An operator-origin rule: only operator-labelled samples
  count (section 12.2). Rule-made decisions are excluded —
  the item never queued, so no operator judgement of it
  exists, and scoring it would be the rule grading itself.
  A later operator reject of the shape is a labelled sample
  with outcome deny: it counts against a rule predicting
  allow in every stage, including production scoring, so
  operator feedback demotes as well as promotes — the loop
  closes in both directions.

## 14. State export bundles

A state export bundle moves portable state between kernels.
Its format id is `jacquard/state-export/1`; its top-level keys
are exactly `format`, `exported_from`, `config`, `definitions`,
`machines`, `rules`.

- `config` (keys: exactly `units`) travels as-is: the
  destination applies the unit values as one execution entry of
  writes, under an `import` entry recording the bundle hash and
  the export provenance.
- `definitions` (keys per item: exactly `name`, `signature`,
  `body`, `examples`) re-enter through the destination's
  dictionary: examples re-run, computed effects are recomputed
  — a bundle that carries claimed computed effects is refused.
- `machines` (parsed form, section 10) re-enter through the
  destination's profile checker.
- `rules` (keys per item: exactly `rule_id`, `definition`,
  `shape`, `predicted_outcome`, `support`, `dominance_bp`,
  `origin`, `stage_at_export`) travel UNPROVEN: `stage_at_export`
  is provenance, recorded on the imported rule as
  `imported_from_stage`, and has no effect on the imported
  stage. Every imported rule re-enters at shadow and must
  re-earn promotion on the destination's own record.

What never travels: authority, credentials, standing, budgets.
The destination issues its own budgets. The importer refuses,
with PROVENANCE: a bundle of the wrong format; unknown keys at
the top level or in any item; any key named like a credential,
secret, token, authority, budget, standing, or stage (other
than the provenance field `stage_at_export`) anywhere in the
bundle's structural sections (config, machines, rules,
exported_from — definition bodies are code and are governed by
the dictionary, not by this scan); and any definition, machine
or rule whose name already exists in the destination with
different content. Identical content is skipped, so importing
the same bundle twice is safe.

### 10.5 Executors

The kernel records dispatched actions; executing them is
deployment work, done by executor adapters outside the kernel.
The contract: an action's dispatch payload is a map
`{"cmd": [argv...], "compensate": [argv...]}` (compensate
optional). The action id — `<proposal-id>/action-<n>`, where n
is the dispatch's index among the proposal's dispatch requests
— is the action's idempotency key: an executor journals every
run under that id BEFORE reporting, so duplicate delivery (or
a crash between running and reporting) re-reports the recorded
outcome and never re-runs the command. Exit code 0 is reported
as `confirm`; any other outcome as `fail`, followed by running
the compensate command (when present) and reporting
`compensate`. Commands run sandboxed (the reference adapter
uses bubblewrap where available — read-only root, private
temporary directory, no network — and says so in its journal;
a fallback sandbox is recorded as a fact, never silently).

## 15. Chain-head anchoring

The hash chain of section 2 proves a log is *self-consistent*: every
hash recomputes and every `prev` links. It does not prove the log is
*the* history. Whoever holds a log can rewrite any entry, recompute
the chain from that point on, and present a fully self-consistent
forgery — chain verification alone cannot tell the two apart. This
section closes that hole with *anchoring*: signed checkpoints of a
log's prefix, published outside the kernel's store, so a third party
can verify a presented log against history the operator cannot
silently rewrite. (This is the mechanism behind the void scan's V3:
a "why was this allowed" record verifiable without trusting the
vendor. A claim of immutability is not a mechanism; this is.)

Anchoring is operator and deployment work, outside the kernel —
like executors (section 10.5), the kernel itself never anchors,
never holds a key, and imports no signing code. The kernel's log
format does not change: a checkpoint is not a log entry (the
`checkpoint` entry kind of section 2 is an in-log state hash and
witnesses nothing outside the log).

### 15.1 The checkpoint document

A checkpoint is a small signed JSON document. The signed part is
the *body*, an object with exactly these eight keys — a body
carrying any other key, or missing one, is not a checkpoint and a
verifier must refuse it:

- `format`: the string `jacquard/anchor/1`.
- `log_id`: hex64, the identity of the anchored log (section 15.2).
- `label`: a string, operator-chosen (for example
  `proof-run-2/kernel`). The label is signed but *informational*:
  it helps a human find the log; identity never rests on it.
- `checkpoint_seq`: integer ≥ 0. Checkpoints for one `log_id`
  form their own sequence, starting at 0, incrementing by 1, with
  no gaps.
- `log_length`: integer ≥ 0, the number of log entries the
  checkpoint anchors — a prefix length.
- `head_hash`: hex64, the hash of the entry at `log_length - 1`,
  or 64 zero characters when `log_length` is 0.
- `spec`: the version of *this section* under which the
  checkpoint was issued — `jacquard/0.5` for checkpoints issued
  under spec 0.5, `jacquard/0.6` from spec 0.6 on. The anchor
  format (`jacquard/anchor/1`) did not change in 0.6, so a
  verifier conforming to this section must accept either value
  and must refuse any other. The anchored log's entries may
  carry any earlier spec version; the checkpoint's `spec` is
  the anchoring protocol's version, not an entry's.
- `prev_checkpoint`: hex64 or null — the section-1 hash of the
  previous checkpoint *body* for the same `log_id`; null if and
  only if `checkpoint_seq` is 0. The checkpoint sequence is
  therefore itself a hash chain: a published checkpoint cannot be
  dropped, reordered or replaced without breaking the chain a
  verifier recomputes.

What is signed is exactly the canonical bytes (section 1) of the
body object — no prefix, no envelope, no transport bytes. The
signature scheme is Ed25519 (RFC 8032) over those bytes.

The *document* (the file form, and the form a transport carries)
is the envelope object `{"body": <body>, "pubkey": <hex64>,
"sig": <hex128>}`, where `pubkey` is the signer's raw 32-byte
public key as lowercase hex and `sig` is the 64-byte signature as
lowercase hex. The file form is the canonical bytes (section 1)
of the envelope followed by a newline. The *checkpoint hash* of a
checkpoint — the value `prev_checkpoint` chains to — is the
section-1 hash of its body.

The golden vectors (section 9) carry one checkpoint, issued for
the vector entry chain under a published test key whose seed is
recorded in the vectors themselves. That key is a test fixture,
never an operator key.

### 15.2 Identity of a log

A checkpoint names its log by `log_id`: the hash of the log's
genesis entry (`entries[0].hash`). For an empty log, `log_id` is
64 zero characters. Anchoring an empty log is permitted and
vacuous (`log_length` 0, `head_hash` all zeros).

This is a deliberate, stated limitation: `log_id` names a
*lineage* (a genesis), not an instance. Two logs that share a
genesis share a `log_id`; that is not a defect, because identity
never does the security work — the binding is the
(`log_length`, `head_hash`) pair, which names one exact prefix.
`log_id` scopes a checkpoint history and gives the verifier its
genesis check (section 15.5, step 2): a history whose `log_id`
differs from the presented log's genesis is *not applicable* to
that log, however it was obtained.

### 15.3 The signing key

One Ed25519 keypair per operator (a deployment may use one per
log; the reference tooling uses one per operator). Key
management is a product surface, not a bare file: the private
key is passphrase-protected at rest, rotation is a recorded
event in the witness transport with continuity of verification,
and the compromise story below is the one the tooling actually
implements.

- *Generation.* The operator generates the keypair with the
  anchor tool's `keygen` verb. The reference implementation uses
  the `cryptography` package — the anchoring tooling's only
  non-standard-library dependency, confined to that tooling; the
  kernel remains zero-dependency and imports none of it.
- *Where the private key lives, and how it is protected.* At
  `~/.jacquard/anchor-key.ed25519` (a PEM-encoded PKCS#8 private
  key, file mode 0600), outside every repository. The tool
  refuses to overwrite an existing key and refuses a key path
  inside a version-controlled tree. From spec 0.6 the key is
  **encrypted at rest** (PKCS#8 with the cryptography package's
  best-available encryption, currently scrypt + AES-256-CBC):
  `keygen` requires a passphrase and refuses to write an
  unencrypted key. The passphrase is supplied at run time only —
  from the `JACQUARD_ANCHOR_PASSPHRASE` environment variable, or
  by an interactive prompt on the terminal when no variable is
  set. It is never taken from a command-line argument (argv is
  world-readable on a multi-user machine), never printed, never
  logged, and never committed. Every verb that signs (`anchor`,
  `rotate`) unlocks the key per run; nothing caches it. A key
  file written before 0.6 is unencrypted PEM: the tool still
  loads it (a deployment mid-migration must be able to anchor),
  but `keygen` and `rotate` never produce one, and rotating —
  the migration path — replaces it with an encrypted successor.
  The public key is not secret: it is published in the anchor
  transport (section 15.4) and carried in every checkpoint
  envelope.
- *What the signature does and does not rest on.* A verifier
  trusts a public key pinned out-of-band (obtained from the
  operator, or from the anchor repository's key registry through
  a channel the verifier already trusts). The `pubkey` field in
  an envelope is a convenience for matching, never self-trust:
  a verifier must refuse a checkpoint whose envelope key is not
  the scheduled key for its sequence (below).
- *The key registry.* The anchor transport carries a registry
  file, `keys.json` at the transport root, of the form
  `{"format": "jacquard/anchor-keys/2", "keys": [...]}`. Each
  entry is `{"pubkey": hex64, "status": "active" | "retired",
  "signs_from": {<log_id>: first checkpoint_seq},
  "signs_until": {<log_id>: last checkpoint_seq}}`. A `log_id`
  omitted from one map is unbounded on that side; a `log_id`
  omitted from BOTH maps is a null window \u2014 the key signs
  nothing for that log and contributes no window to its
  schedule. ERRATUM (2026-11-03, spec 0.6 erratum 2): the /1
  grammar had no null window \u2014 every key participated in
  every log's schedule, an omitted side meaning unbounded
  \u2014 so no /1 registry could schedule a log born after a
  rotation and signed only by a successor the retired key
  never named. Verifiers MUST accept /1 registries under the
  legacy rule stated for them (every key participates, omitted
  sides unbounded) and /2 registries under the null-window
  rule, and MUST refuse a registry of any other format by
  name. The change is confined to the registry document, which
  carries its own format version for this reason: no
  checkpoint, entry or seal byte changes, so the spec seal
  and every recorded hash stand.
  Entries are ordered by first use. The registry is how a
  verifier learns the *schedule*: for a presented log, the key
  scheduled for a checkpoint is the entry whose window for that
  `log_id` covers its `checkpoint_seq`. Windows for one `log_id`
  must partition its checkpoint sequence — every sequence is
  covered by exactly one key — or the registry is malformed and
  a verifier must refuse it. The registry is data in a public,
  append-only transport: its own git history witnesses when
  each key was published, and a registry that contradicts the
  checkpoints actually published (a window claiming a key signed
  a sequence its envelopes do not carry) fails verification of
  those checkpoints, because the envelope key must equal the
  scheduled key. `pubkey.txt` is retained for compatibility: it
  names the *current* active key, nothing more.
- *Rotation.* Rotation is: generate a successor keypair
  (encrypted, as above); publish the successor's public key in
  the registry with `signs_from` set, for each `log_id` being
  rotated, to the next unpublished `checkpoint_seq`, and set
  the predecessor's `signs_until` for that `log_id` to the last
  sequence it signed; publish a rotation note in the transport
  README recording the same boundary in prose; then sign the
  next checkpoint — at or after the boundary — with the
  successor. The checkpoint body's `prev_checkpoint` chain is
  key-agnostic: it links the last old-key checkpoint to the
  first new-key checkpoint, so the history's continuity is
  itself hash-chained across the rotation. Checkpoints before
  the boundary verify under the old key, checkpoints from the
  boundary under the new, and a verifier must refuse an old-key
  checkpoint at or after it (and a new-key checkpoint before
  it). The retired private key is kept, encrypted, outside any
  repository, only as long as re-anchoring under it could ever
  be required — which, once the boundary is published, is
  never: a deployment should destroy it, and says in the
  rotation note whether it did. The reference tooling takes the
  pinned key(s) as explicit verifier inputs — `--pubkey`, or
  `--rotation-seq` + `--rotated-pubkey`, or the registry via
  `--keys` — and never silently follows a key change.
- *Compromise.* Whoever holds the private key *and* its
  passphrase can issue checkpoints for any prefix of any log —
  including checkpoints that appear to anchor a forged history.
  Encryption at rest is what the passphrase buys: a copied key
  file alone is not the key. Compromise does not let an attacker
  rewrite checkpoints *already published* to a public transport
  without detection by anyone who mirrored that transport
  (section 15.4); it poisons checkpoints issued after the
  compromise. The response to a suspected compromise is a
  rotation (above) plus a compromise note in the transport
  naming the first `checkpoint_seq` (per `log_id`) from which
  the old key's checkpoints must no longer be trusted; verifiers
  treat that note, read through a trusted channel, as a
  registry amendment. There is no trusted clock in a checkpoint
  (the body carries no wall-clock field — deliberately, for the
  reason stated in section 15.4), so "issued before the
  compromise" cannot be proven from the document alone; it
  rests on the transport's publication record.

### 15.4 Cadence and transport

*Who and when.* Anchoring is an operator-run verb; nothing
anchors automatically. The recommended cadence — a recommendation
of this section, stated so the gap is a choice and not a
surprise — is: anchor at the end of every operator session or
proof run in which the log grew, at least once per day a log is
actively growing, and always before a log is handed to a third
party or relied on in a dispute. The entries after the last
anchored length are the *unanchored tail*: real history, but
history only the log's holder vouches for. Verification reports
the tail's length numerically (section 15.5); a deployment picks
its cadence to bound the tail it can accept.

*Transport.* The mechanism is transport-agnostic. A conforming
transport is any store outside the kernel's and the log holder's
sole control where checkpoint documents are append-only in
practice: new documents can be added, and rewriting or removing
a published document is detectable by a third party who mirrored
the store. The signed body carries no wall-clock field, because
Jacquard has no trusted clock (its clock is the log itself);
existence-at-a-time is therefore proven by the transport's
publication record (for git, the commit that first carries the
checkpoint), never by a signed timestamp an operator could write
arbitrarily.

*First transport: a dedicated public git repository* (the
reference deployment is `SuperInstance/jacquard-anchors`,
separate from the kernel repository, so the witness history is
not the witnessed history's own repo). Layout: one file per
checkpoint at `checkpoints/<log_id>/<checkpoint_seq>.json` with
`checkpoint_seq` zero-padded to six digits, containing the file
form of section 15.1. The publisher only ever *adds* commits —
one commit per checkpoint, adding exactly that checkpoint's file
— and never amends, rebases or force-pushes; the repository's
README records the operator public key (and any rotation note)
and how to verify. A publisher history that violates the
append-only discipline is itself evidence a verifier should
weigh, and mirrors of the repository make a silent rewrite
detectable in exactly the way a silent log rewrite is not.

### 15.5 Verification

Inputs: a presented log; a checkpoint history (a set of
checkpoint documents, from any conforming transport); the pinned
key schedule for the log — a single public key, a key plus a
rotation boundary, or the key registry of section 15.3 read from
the transport. No private
key, no kernel state, and no trust in the log's holder are
required. The procedure, in order:

1. *Select and authenticate the history.* Take the checkpoints
   whose `log_id` equals the presented log's genesis hash
   (section 15.2); ignore others. Sort by `checkpoint_seq` and
   require the sequence to be 0, 1, 2, … with no gaps, each
   body's `prev_checkpoint` recomputing to the previous body's
   hash (null at 0), each body's keys exactly the eight of
   section 15.1 with `format` as stated and `spec` either
   `jacquard/0.5` or `jacquard/0.6` (section 15.1), each
   envelope's `pubkey` equal to the key the schedule assigns to
   its `checkpoint_seq` (section 15.3), and each signature
   verifying over the body's canonical bytes. Any failure is FAILED, naming the
   offending `checkpoint_seq`.
2. *Genesis check.* If the presented log is non-empty, its first
   entry's hash must equal the history's `log_id` (it does by the
   selection in step 1, unless the history was supplied as an
   explicit set for a different log — then FAILED, naming the
   mismatch). If no checkpoint is applicable, the outcome is
   UNANCHORED: a statement that nothing witnesses this log, not a
   failure of the log.
3. *Internal chain.* Verify the presented log's own chain
   (section 2). A log that fails its internal chain is FAILED
   (internal), reported distinctly from an anchor failure.
4. *Prefix comparison.* For each checkpoint in sequence order:
   if `log_length` exceeds the presented log's length, the log is
   truncated or missing anchored history — FAILED, naming that
   checkpoint. Otherwise compute the head at `log_length` (the
   hash of the entry at that index minus one; all zeros at 0) and
   compare with `head_hash`. On the first mismatch: FAILED,
   naming that checkpoint as the *first divergent checkpoint*
   (its `checkpoint_seq`, its `log_length`, the expected and
   actual heads). A checkpoint binds only its prefix: a rewrite
   after `log_length` cannot fail this checkpoint — it is tail,
   and step 5 reports it as such.
5. *Outcome.* If every checkpoint passes: when the last
   checkpoint's `log_length` equals the presented length, the
   outcome is VERIFIED (fully anchored, tail 0). When it is
   smaller, the outcome is VERIFIED-TO-ANCHOR, reporting the
   anchored prefix length and the unanchored tail length
   (presented length minus anchored length) as distinct numbers.
   An extension of an anchored log — same prefix, more entries —
   is therefore not a forgery and must not be reported as one;
   truncation below an anchored length is a failure (step 4),
   never a tail.

A verifier reports exactly one outcome — VERIFIED,
VERIFIED-TO-ANCHOR (with both lengths), UNANCHORED, or FAILED
(with the first divergent checkpoint, or the history/internal
failure, named) — never a bare boolean.

### 15.6 Honest limits

Anchoring proves a bounded thing, and this section states the
bound. It proves that a specific log prefix existed in exactly
that form no later than its checkpoint's publication on the
transport, and it detects any later rewrite of the anchored
prefix that changes the head at an anchored length — including
the rewrite-and-rechain forgery that defeats section 2 alone. It
does not prove the decisions in the log were wise, lawful or
authorised beyond what the log itself records; it does not prove
anything about the unanchored tail; it does not prove the
presented log is complete — an operator may anchor a prefix of a
longer private history, and withholding beyond the anchored
length is invisible (withholding *within* it is exactly what the
head comparison catches); it does not prevent an operator from
abandoning a log and starting a new one under a new genesis (the
new `log_id` is visibly a new history, with no checkpoints until
anchored); and it does not survive the private key and the
transport's history being rewritten together — mirrors are the
defence there, as section 15.4 states. A checkpoint for a log
that is never presented proves only that its head was claimed by
the key holder; the verification of section 15.5 is what turns a
claim into evidence.

## 16. Sealed exports

Anchoring (section 15) makes a log verifiable without trusting
its holder. It says nothing about *disclosure*: a log that can
be verified can also be read, and some fields in a real log —
who released a queued item, whose name a proposal carries —
should not travel with every copy. This section defines
*sealing*: designated fields are redacted in an **export** such
that the export still verifies. Sealing is export tooling,
outside the kernel, like anchoring: the kernel never seals, and
the log format changes only by the addition of the `seal` entry
kind (section 2), which has no fold effect.

The load-bearing rule: **redaction is a view, not a rewrite.**
The anchored log itself is never altered by sealing. A seal is
committed *in the log* before any export relies on it, so the
decision to redact — which fields, under which class — is
itself part of the anchored record, not an edit performed on
the way out.

### 16.1 Seal entries

A `seal` entry's body is `{"producer": str, "seals": [seal]}`,
where each seal is an object with exactly these keys:

- `entry_seq`: integer — the entry whose field is sealed. It
  must be strictly less than the seal entry's own `seq` (a seal
  names history, never the present or the future), and the
  named entry's kind must not be `seal` (seals do not seal
  seals).
- `field`: a dotted path resolving inside the named entry's
  *body* (for example `released_by`, or `requests.command`).
  Structural fields (`seq`, `prev`, `hash`, `spec`, `kind`) are
  not sealable: paths resolve in the body only. Each path
  element names an object key, or a non-negative integer index
  into an array.
- `class`: a short string naming the *class* of the sealed
  value (for example `operator-identity`, `personal-name`,
  `credential`). The class is disclosed by design — an export
  names what classes of field were sealed, without revealing
  values — and it is therefore metadata: a coarse class over a
  population of one can identify. Deployments choose classes
  coarse enough for their population, and section 16.4 states
  the limit plainly.
- `mode`: `hash` or `keyed` (below).
- `commitment`: hex64, binding the sealed value as follows.
  Let `preimage` be the object `{"domain": "jacquard/seal/1",
  "entry_seq": <entry_seq>, "field": <field>, "value": <the
  original value>}`. In `hash` mode the commitment is the
  section-1 hash of `preimage`. In `keyed` mode the commitment
  is the hex HMAC-SHA-256, under a *redaction key* held by the
  operator outside any repository, of the canonical bytes of
  `preimage`. The modes differ in who can check a commitment
  against a candidate original (section 16.3) and in what the
  commitment hides (section 16.4); they are identical in
  structure everywhere else.

A seal is a claim by its producer, committed at its entry's
position in the chain: the entry hash of the seal entry — and
therefore, once anchored, the checkpoint head — binds the exact
set of (entry, field, class, mode, commitment) tuples. A seal
computed over a *different* value than the field actually holds
is a lie the log's holder told in advance; it is detectable by
anyone who later holds both the original log and (for `keyed`
mode) the redaction key, and section 16.4 is explicit that
export verification alone does not detect it.

### 16.2 The export document

A redacted export is a single JSON document (the canonical
bytes of the object, plus a newline, in file form):

- `format`: the string `jacquard/redacted-export/1`.
- `log_id`: hex64, the source log's identity (section 15.2).
- `source_length`: the length of the log the export was made
  from, seal entries included.
- `exported_length`: the number of entries the export carries.
  An export carries a **prefix** of its source — entries
  `0 .. exported_length - 1`, contiguous, in order — never a
  selection. Prefix-only is what makes omission checkable:
  dropping a seal entry (or any entry) breaks the sequence,
  the `prev` chain, and the head comparison of section 16.3.
- `seal_set_hash`: the section-1 hash of the list of *applied*
  seals — every seal in the carried seal entries whose
  `entry_seq` is below `exported_length` — each represented as
  `{"entry_seq", "field", "class", "mode", "commitment"}`,
  sorted by (`entry_seq`, `field`). A verifier recomputes it;
  an export whose seals were quietly edited fails here before
  any entry is examined.
- `entries`: the carried entries. Each entry is the original
  entry object (`seq`, `prev`, `kind`, `body`, `spec`, `hash`)
  with exactly one change: at each sealed position, the value
  is replaced by the *marker* object `{"sealed": <commitment
  hex64>, "class": <class>}`. The entry's `hash` field is the
  **original** entry hash, retained verbatim — it is the hash
  of the unredacted entry, and a redacted body cannot recompute
  it. Nothing else differs: unsealed fields, unsealed entries,
  order, and hashes are the original's.

An export with no seals applied is the identity view; the
format still holds and verification reduces to section 15.5
over the carried prefix.

### 16.3 Export verification

Inputs: an export document; a checkpoint history and key
schedule as in section 15.5; optionally the redaction key (for
`keyed` commitments). No trust in the export's presenter is
required. The procedure, in order:

1. *Header.* `format` as stated; `log_id` equals the genesis
   entry's retained hash (all zeros if the export is empty);
   `exported_length` equals the number of carried entries and
   does not exceed `source_length`; `seal_set_hash` recomputes
   from the seal entries carried in the export (a seal naming
   an entry at or beyond `exported_length` is not applied and
   does not enter the set). Any failure is FAILED (header).
2. *Linkage.* Carried entries are in `seq` order `0, 1, 2, …`
   and each entry's `prev` equals the previous entry's retained
   `hash` (genesis `prev` is all zeros). Any failure is FAILED
   (linkage).
3. *Unsealed entries recompute.* For every carried entry with
   no sealed position: the section-2 hash of
   `{seq, prev, kind, body, spec}` must equal the retained
   `hash`. Seal entries are unsealed by construction (section
   16.1) and are checked here like any other entry. Any failure
   is FAILED, naming the entry's `seq`.
4. *Sealed entries are consistent.* For every carried entry
   with sealed positions: each position must carry a marker,
   the marker's commitment and class must exactly match an
   applied seal for that (`entry_seq`, `field`), and every
   applied seal must be used by exactly one marker — a sealed
   field presented in clear, an unsealed field replaced by a
   marker, and a marker with no committed seal are each FAILED,
   naming the entry and field. The retained hash of a sealed
   entry is *not* recomputed; it is authenticated transitively:
   the next entry's `prev` names it, every later unsealed entry
   recomputes over a chain that passes through it, and step 5
   compares the resulting heads against signed checkpoints.
   Precisely: the binding comes from linkage + anchoring; this
   step is a consistency check between the view and the seals
   the log committed, not a proof by itself.
5. *Anchor comparison.* Run the checkpoint-history
   authentication of section 15.5 step 1 unchanged, then the
   prefix comparison of step 4 using the retained hashes:
   for each checkpoint with `log_length` at or below
   `exported_length`, the retained hash at that length must
   equal the checkpoint's `head_hash`; the first mismatch is
   FAILED, naming that checkpoint as first divergent.
   Checkpoints beyond `exported_length` are out of scope for a
   prefix export and are reported as `checkpoints_beyond`, not
   treated as truncation (the export declares its prefix; a
   presented *log* that stops short of an anchored length is
   truncation, section 15.5 — an export that declares a shorter
   prefix is a view of one).
6. *Commitment checking (optional, stated in the result).* A
   verifier holding the original log checks each applied seal's
   commitment against the true field value: directly in `hash`
   mode, with the redaction key in `keyed` mode. A verifier
   without the original checks consistency only (steps 1–5).
   The result states which was done: `commitments_checked` is
   `full` (an original was supplied and every commitment
   recomputed), `keyed` (the redaction key was supplied and the
   original — keyed commitments cannot be checked without
   both), or `consistency` (neither).
7. *Outcome.* Exactly one of: `verified` (every checkpoint at
   or below `exported_length` passed and the greatest anchored
   length equals `exported_length`), `verified_to_anchor`
   (checkpoints passed; the result reports `anchored_length`
   and `unanchored_tail` = `exported_length -
   anchored_length` as distinct numbers), `unanchored` (no
   checkpoint applies to this `log_id`), or `failed` (with the
   stage and the first divergent checkpoint or entry named) —
   the same vocabulary as section 15.5, never a bare boolean.
   The result also reports `seals_applied` (count),
   `seals_anchored` (true iff every applied seal's seal entry
   lies within the anchored prefix — a seal in the unanchored
   tail is a commitment only the log's holder vouches for
   until the next checkpoint covers it), and
   `commitments_checked` as above.

Tamper evidence, stated exactly: flipping a marker's commitment
fails step 4 (no committed seal matches); editing the matching
seal fails step 3 (the seal entry no longer recomputes) or step
1 (the seal-set hash); changing a retained hash fails step 2 or
step 5; changing any unsealed field fails step 3. Rebuilding a
fully consistent forgery requires a chain whose head at an
anchored length equals the signed checkpoint's — a preimage
attack on SHA-256 — or the anchor key.

### 16.4 Honest limits

Sealing proves that a redacted view is a faithful redaction —
under committed seals — of an anchored log. It does not prove
more, and this section states the rest.

- **A commitment is a binding, not an encryption.** In `hash`
  mode, anyone holding the export can test candidate values
  against a commitment; for low-entropy values (a role string,
  a name from a small population) the value is recoverable by
  enumeration and the seal hides nothing — it only stops the
  value propagating in clear and proves consistency. `keyed`
  mode removes the enumeration attack for parties without the
  redaction key, at the price that those parties get
  consistency, not correctness (step 6). Where a value must
  stay secret from the export's audience outright, the honest
  options are a coarser export (do not carry that entry range)
  or no export; sealing is not a confidentiality primitive.
- **The class is disclosed.** An export names the classes of
  field sealed, as section 16.1 states; over a small population
  a class can identify. That is a stated tradeoff of making the
  redaction itself auditable, not an oversight.
- **Seals in the tail are unanchored.** Until a checkpoint
  covers the seal entry, `seals_anchored` is false and the seal
  set rests on the log holder's word, exactly like the tail it
  sits in (section 15.4). An audience that needs anchored seals
  waits for the next anchoring run; the verification result
  says which case it is in, numerically.
- **The operator chose the seals.** Sealing is the operator's
  redaction decision, committed and therefore auditable, but
  nothing forces an operator to seal a field an audience
  believes was sealed. The seal set is visible in the log; a
  dispute about what *should* have been sealed is a governance
  question the record informs, not one the mechanism settles.
- **The public demonstration seals public values.** The
  reference live run seals fields of the published proof-run
  log, whose values are already public; it demonstrates the
  mechanics and the verification, and claims no confidentiality
  for those values. The confidentiality-relevant case — a
  private log, a shared export — is the design's target, and
  its limits are the ones above.

## 17. Consumption pricing (deployment policy note)

NOTE (2026-11-03, spec 0.6 erratum 3): this section is a
deployment-policy note, not kernel semantics. It constrains
no conforming kernel; it records the semantics the
reference deployment (the gpu-queue bridge) implements in
`adapters/consumption.py`, so that a shadow score and a
live decision are the same arithmetic. The kernel's own
downstream-use sense (section 11.3) is unchanged.

A consumption policy prices a producer's submissions to a
governed job class by the producer's trailing output-use
ratio, computed from the log, strictly causally (a
submission is priced only on entries recorded before it):

- A producer's completed outputs are the declared outputs
  of its submissions whose producing job's completion is
  recorded in the log. An output counts as USED only when
  a consuming job whose completion is also recorded named
  it in its execution entry's uses. A use declared at a
  consumer's submission but never completed — including a
  consumer that failed — counts for nothing (completed
  consumption only; no promise flattery).
- Cold start is an EXEMPTION BUDGET denominated in
  completed outputs (reference value 3, policy data):
  while a producer's completed-output count is below the
  budget, its submissions are exempt from a consumption
  hold, and each exemption actually spent is recorded as a
  claim in the policy's accounting (the per-item policy
  sense entry, when live). Once the budget is exhausted
  the ratio rules; it is then defined by construction.
- A submission is held when it declares an output with no
  declared consumer in an earlier execution entry, the
  budget is exhausted, and the ratio is below the
  threshold (reference value 5000 basis points, policy
  data). Held items enter the batched decision queue like
  any other hold; the operator's release or reject is the
  decision of record.

Known residual, stated at adoption: the policy has no
marker for a declared successor/sentinel job — a job whose
purpose is to stand queued — and will price one as
ordinary production until such a marker exists in the
policy record.
