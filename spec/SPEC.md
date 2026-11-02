# Jacquard specification — version 0.2

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
- Strings are escaped in the ASCII-safe form: `"` and `\` are
  backslash-escaped; backspace, form feed, newline, carriage
  return and tab use their short escapes (`\b`, `\f`, `\n`,
  `\r`, `\t`); every other character outside printable ASCII
  — including ALL non-ASCII characters — is escaped as
  `\uXXXX` with lowercase hex digits, astral characters as
  surrogate pairs. (The golden vectors include a non-ASCII
  checkpoint name so this rule is exercised, not just stated.)
- The hash of a structure is the lowercase hex SHA-256 of its
  canonical bytes.

## 2. The log

The log is an append-only sequence of entries. State is a fold of
the log; the log is never rewritten.

Entry: `{"seq": int, "prev": hex64, "kind": str, "body": object,
"spec": "jacquard/0.2"}`. The entry hash is the hash of the entry.
`prev` is the previous entry hash; the genesis entry has
`prev` = 64 zero characters. `seq` starts at 0 and increments by 1.

Entry kinds: `proposal`, `decision`, `definition`, `execution`,
`sense`, `checkpoint`, `machine`, `transition`, `budget`, `price`,
`rule`, `import`. The entry hash is the hash (section 1) of the
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
  the stored work), `releases` / `rejects` / `expires` plus
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

## 3. Envelopes and verdicts

Producers submit envelopes:
`{"v": 1, "id": str, "producer": str, "kind": str, "body": object,
"declared_effects": [str], "spec_seal": hex64}`.
`id` is an idempotency key: resubmitting the same envelope returns
the original verdict and appends nothing. `spec_seal` is the hash
of the raw UTF-8 bytes of the string `jacquard-spec/0.2` (not of its canonical JSON form). The envelope id used in the log
is the hash of the envelope.

Envelope kinds: `proposal` (body: `{"requests": [request]}`),
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
UNREACHABLE, DEAD, AMBIGUOUS, NON_TOTAL. Every refusal is itself recorded in the log as a
`decision` entry.

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
both close the queue item without executing it.

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
implements sections 1-5 compatibly.

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
12's business, and the stub's method says so).

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
where shape is (producer, class, exact effect set) and
definition names a pure dictionary word — the *recogniser* —
that decides whether a proposal matches the shape. A rule's
identity is a hash of its shape and prediction: identity is
derived from instances, not assigned. A rule's stage is never
stored in the rule entry; it is the state of the rule's
standing-rule machine instance, whose id is the rule id.

The pipeline:

1. *Mining.* Primary decisions (the first decision per proposal;
   release/reject/expire follow-ups and fault records are not
   fresh evidence) are grouped by shape over a training window
   (reference: the first 70%). A shape with at least the minimum
   support (reference: 3) and a dominant outcome (reference:
   ≥80% of its decisions) becomes a candidate.
2. *Offline evaluation.* The candidate's prediction is scored
   against the held-out tail. Below the bar (reference: 80%
   agreement) it stays a candidate; the scores are recorded on
   the rule entry either way.
3. *Shadow.* The rule predicts but never decides. Agreement with
   real outcomes is scored from the log.
4. *Canary, then active.* Promotion at each stage requires
   scored agreement (reference: ≥90% over ≥3 fresh samples at
   that stage). There is no faster lane for shapes carrying
   protected effects.
5. *Production scoring and demotion.* An active rule decides
   matching proposals through the sequencer's rule hook, within
   bounds: it never overrides a suspension, and it never turns
   an outcome into a queue. Every rule-made decision records
   `decided_by` and `policy_outcome` (what the policy gate would
   have done), so scoring compares the rule against the
   constitution. An active rule whose agreement over fresh
   samples collapses (reference: <50% over ≥5) is demoted
   automatically — the regress transition and the scores are in
   the log.
6. *Revocation.* One call steps the rule to revoked. The hook
   reads stage from folded state per proposal, so revocation
   takes effect on the next proposal and decides nothing further.

Scoring in every stage counts, per matching primary decision,
agreement between the prediction and the actual outcome — where
"actual" for a rule-made decision is the recorded policy
outcome, never the rule's own decision.

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
