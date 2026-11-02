# Jacquard specification — version 0.2

This document is the contract. Conforming implementations must
reproduce the golden vectors in `spec/vectors/` exactly. The Python
code in `src/jacquard/` is the reference implementation of this
version.

## 1. Canonical serialisation

All hashed or stored structures use one canonical JSON form:

- UTF-8, keys sorted, separators `,` and `:` (no whitespace).
- Values are restricted to: null, true, false, integers, strings,
  arrays, objects. **No floating-point numbers.** Quantities that
  would be fractional are integers in a stated unit (weights are
  milli-units, durations are milliseconds).
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
`rule`, `import`. A checkpoint body is `{"name": str,
"state_hash": hex64}` where state_hash is the hash of the folded
state at that point.

Folded state:
- `units`: committed key/value state, changed only by applied
  `write` effects recorded in `execution` entries.
- `dictionary`: definitions, by name, as a list of versions.
- `decision_queue`: proposals whose decision outcome was `queued`,
  by proposal id, until an operator decision releases or rejects
  them.
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

## 3. Envelopes and verdicts

Producers submit envelopes:
`{"v": 1, "id": str, "producer": str, "kind": str, "body": object,
"declared_effects": [str], "spec_seal": hex64}`.
`id` is an idempotency key: resubmitting the same envelope returns
the original verdict and appends nothing. `spec_seal` is the hash
of the string `jacquard-spec/0.2`. The envelope id used in the log
is the hash of the envelope.

Envelope kinds: `proposal` (body: `{"requests": [request]}`),
`definition` (body: a definition, section 5), and `machine`
(body: `{"text": <machine definition text>}`, section 10).

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
"requests", "outcome"}`. Firing order for a (state, event): the
guarded transition first (its guard word is evaluated against the
event payload map; it fires iff it leaves exactly `[true]`), then
a plain transition, then the `otherwise` fallback. Outcomes:
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
  steps decide, commit, close.
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
