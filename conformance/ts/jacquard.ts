// Jacquard — independent TypeScript implementation, Phase 3 slice 8.
//
// Written from spec/SPEC.md (version 0.2) ONLY. No reference-implementation
// source was consulted. Scope, per the slice brief: canonical serialisation
// + SHA-256 hashing (spec §1), envelope validation + envelope id (§3),
// log entry construction + hash-chain verification (§2), and the log fold
// producing the folded state and state hash (§2, with the fold effects
// stated in §§5, 7, 10, 11, 12, 14). Dictionary evaluation and sequencer
// execution are out of scope.
//
// Node builtins only. Erasable TypeScript syntax only (no enums/namespaces),
// so Node v24 runs this file with native type stripping.
//
// Every place the spec underdetermines a choice made here is recorded in
// GAPS.md next to this file, cross-referenced as (GAPS.md #n).

import { createHash } from "node:crypto";

export type Json =
  | null
  | boolean
  | number
  | string
  | Json[]
  | { [key: string]: Json };

export type JsonObject = { [key: string]: Json };

function isPlainObject(v: unknown): v is JsonObject {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// ---------------------------------------------------------------------------
// §1 Canonical serialisation
// ---------------------------------------------------------------------------

// Key order: lexicographic by Unicode code point (§1 as amended
// after GAPS.md #1).
function compareKeys(a: string, b: string): number {
  const ac = Array.from(a);
  const bc = Array.from(b);
  const n = Math.min(ac.length, bc.length);
  for (let i = 0; i < n; i++) {
    const d = (ac[i].codePointAt(0) as number) - (bc[i].codePointAt(0) as number);
    if (d !== 0) return d;
  }
  return ac.length - bc.length;
}

// Serialise one value to its canonical JSON text. Only the §1 value set is
// allowed: null, true, false, integers, strings, arrays, objects. Floats,
// undefined, functions, symbols and bigints are rejected, as are integers
// outside the safe-integer range (their decimal form cannot be produced
// reliably from a JS number; GAPS.md #2).
// §1 as amended after GAPS.md #3 and the slice-8 vector round:
// strings are emitted RAW as UTF-8 except the JSON-required
// escapes (" \ and controls below U+0020, short forms where
// they exist, else \u00xx lowercase hex) — exactly JSON.stringify's
// string behaviour. An escaped-non-ASCII reading was drafted and
// the non-ASCII golden vector refuted it: the vector, not the
// draft, is the contract's evidence.
export function escapeString(value: string): string {
  return JSON.stringify(value);
}

export function canonical(value: Json): string {
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (typeof value === "number") {
    if (!Number.isInteger(value)) {
      throw new TypeError(`canonical: non-integer number ${value} is not allowed`);
    }
    if (!Number.isSafeInteger(value)) {
      throw new TypeError(`canonical: integer ${value} is outside the safe range`);
    }
    return String(value);
  }
  if (typeof value === "string") {
    return escapeString(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map((v) => canonical(v)).join(",") + "]";
  }
  if (isPlainObject(value)) {
    const keys = Object.keys(value).sort(compareKeys);
    return (
      "{" +
      keys.map((k) => escapeString(k) + ":" + canonical(value[k])).join(",") +
      "}"
    );
  }
  throw new TypeError(`canonical: unsupported value of type ${typeof value}`);
}

export function canonicalBytes(value: Json): Uint8Array {
  return new TextEncoder().encode(canonical(value));
}

// §1: the hash of a structure is the lowercase hex SHA-256 of its
// canonical bytes.
export function hash(value: Json): string {
  return createHash("sha256").update(canonicalBytes(value)).digest("hex");
}

// SHA-256 of the raw UTF-8 bytes of a bare string (used for the spec seal,
// §3). Note this is NOT the §1 hash of the string as a JSON value, which
// would include the surrounding quotes; the vectors' seal matches the raw
// reading (GAPS.md #4, caught by check a).
export function hashString(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}

// ---------------------------------------------------------------------------
// §3 Envelopes and the spec seal
// ---------------------------------------------------------------------------

export const SPEC_VERSION = "jacquard/0.2";
export const SPEC_SEAL = hashString("jacquard-spec/0.2");
export const GENESIS_PREV = "0".repeat(64);
const HEX64 = /^[0-9a-f]{64}$/;
const ENVELOPE_KINDS = ["proposal", "definition", "machine"];

export interface Envelope {
  v: number;
  id: string;
  producer: string;
  kind: string;
  body: JsonObject;
  declared_effects: string[];
  spec_seal: string;
}

// Validate an envelope against §3's stated shape. Returns a list of
// problems (empty list = valid). The spec does not enumerate envelope
// validation beyond the shape, the seal and the kind set, and does not say
// whether extra keys are forbidden (GAPS.md #5) — extra keys are allowed.
export function validateEnvelope(env: unknown): string[] {
  const problems: string[] = [];
  if (!isPlainObject(env)) return ["envelope is not an object"];
  if (env.v !== 1) problems.push("v must be 1");
  if (typeof env.id !== "string") problems.push("id must be a string");
  if (typeof env.producer !== "string") problems.push("producer must be a string");
  if (typeof env.kind !== "string" || !ENVELOPE_KINDS.includes(env.kind)) {
    problems.push(`kind must be one of ${ENVELOPE_KINDS.join(", ")}`);
  }
  if (!isPlainObject(env.body)) problems.push("body must be an object");
  if (
    !Array.isArray(env.declared_effects) ||
    !env.declared_effects.every((e) => typeof e === "string")
  ) {
    problems.push("declared_effects must be a list of strings");
  }
  if (typeof env.spec_seal !== "string" || !HEX64.test(env.spec_seal)) {
    problems.push("spec_seal must be a hex64 string");
  } else if (env.spec_seal !== SPEC_SEAL) {
    problems.push("spec_seal does not match the seal of jacquard-spec/0.2");
  }
  return problems;
}

// §3: the envelope id used in the log is the hash of the envelope.
export function envelopeId(env: Envelope): string {
  return hash(env as unknown as Json);
}

// ---------------------------------------------------------------------------
// §2 The log: entry construction and hash-chain verification
// ---------------------------------------------------------------------------

export interface EntryBody extends JsonObject {}

export interface Entry {
  seq: number;
  prev: string;
  kind: string;
  body: EntryBody;
  spec: string;
}

// A log entry as stored/transmitted in the fixtures: the entry plus its
// recorded hash under a separate "hash" key.
export interface StoredEntry extends Entry {
  hash: string;
}

export const ENTRY_KINDS = [
  "proposal",
  "decision",
  "definition",
  "execution",
  "sense",
  "checkpoint",
  "machine",
  "transition",
  "budget",
  "price",
  "rule",
  "import",
];

// Build an entry (without its hash). The entry hash is the §1 hash of this
// object; "hash" itself is not part of the hashed object (GAPS.md #6,
// caught by checks b and e).
export function makeEntry(
  seq: number,
  prev: string,
  kind: string,
  body: EntryBody,
): Entry {
  return { seq, prev, kind, body, spec: SPEC_VERSION };
}

export function entryHash(entry: Entry): string {
  return hash({
    seq: entry.seq,
    prev: entry.prev,
    kind: entry.kind,
    body: entry.body as Json,
    spec: entry.spec,
  });
}

export interface ChainResult {
  ok: boolean;
  checked: number;
  failure: string | null;
}

// Verify a chain of stored entries: seq runs 0,1,2,…; each prev is the
// previous entry's recorded hash (genesis prev = 64 zeros); spec is
// "jacquard/0.2"; and every recorded hash recomputes from the entry.
export function verifyChain(entries: StoredEntry[]): ChainResult {
  let prev = GENESIS_PREV;
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e.seq !== i) {
      return { ok: false, checked: i, failure: `entry ${i}: seq is ${e.seq}` };
    }
    if (e.prev !== prev) {
      return { ok: false, checked: i, failure: `entry ${i}: prev mismatch` };
    }
    if (e.spec !== SPEC_VERSION) {
      return { ok: false, checked: i, failure: `entry ${i}: spec is ${e.spec}` };
    }
    if (typeof e.hash !== "string" || !HEX64.test(e.hash)) {
      return { ok: false, checked: i, failure: `entry ${i}: hash is not hex64` };
    }
    if (entryHash(e) !== e.hash) {
      return { ok: false, checked: i, failure: `entry ${i}: hash does not recompute` };
    }
    prev = e.hash;
  }
  return { ok: true, checked: entries.length, failure: null };
}

// ---------------------------------------------------------------------------
// §2 The fold
// ---------------------------------------------------------------------------

export interface Wrapper {
  entry_seq: number;
  entry_hash: string;
  definition: Json;
}

export interface FoldedState {
  units: JsonObject;
  senses: JsonObject;
  dictionary: { [name: string]: Wrapper[] };
  decision_queue: JsonObject;
  machines: { [name: string]: Wrapper[] };
  machine_instances: JsonObject;
  budgets: JsonObject;
  prices: JsonObject;
  rules: JsonObject;
}

export function emptyState(): FoldedState {
  return {
    units: {},
    senses: {},
    dictionary: {},
    decision_queue: {},
    machines: {},
    machine_instances: {},
    budgets: {},
    prices: {},
    rules: {},
  };
}

function asObject(v: Json | undefined): JsonObject | null {
  return isPlainObject(v) ? v : null;
}

function appendWrapper(
  table: { [name: string]: Wrapper[] },
  name: string,
  entry: StoredEntry,
  definition: Json,
): void {
  const list = table[name] ?? [];
  list.push({ entry_seq: entry.seq, entry_hash: entry.hash, definition });
  table[name] = list;
}

// Apply one entry to the folded state, following exactly the fold rules the
// spec states (§2's state description plus §§5, 7, 10.3, 11.2, 11.3, 12, 14).
export function applyEntry(state: FoldedState, entry: StoredEntry): void {
  const body = entry.body;
  switch (entry.kind) {
    case "proposal":
      // §2 lists no folded component that a proposal entry itself changes:
      // its consequences arrive as decision/execution entries.
      break;

    case "decision": {
      // §2 / §7: a decision whose outcome was queued puts the proposal in
      // the decision queue, keyed by proposal id, storing the full body of
      // the decision entry that queued it. The literal outcome string is
      // not pinned down (§2 says "queued", §7's gate returns "queue"), so
      // both are accepted (GAPS.md #7; no check covers a queued outcome).
      if (
        (body.outcome === "queued" || body.outcome === "queue") &&
        typeof body.proposal_id === "string"
      ) {
        state.decision_queue[body.proposal_id] = body as Json;
      }
      // §7 / §10.4: releases / rejects / expires each carry the proposal id
      // of the queue item they close, exactly like `releases` does.
      for (const field of ["releases", "rejects", "expires"]) {
        const target = body[field];
        if (typeof target === "string") delete state.decision_queue[target];
      }
      break;
    }

    case "definition": {
      // §2 / §5: definitions by name, as a list of version wrappers; the
      // stored form is the definition carried in the entry body.
      const def = asObject(body.definition as Json);
      if (def && typeof def.name === "string") {
        appendWrapper(state.dictionary, def.name, entry, body.definition as Json);
      }
      break;
    }

    case "execution": {
      // §2: units change only via applied `write` effects; budgets lose
      // the priced cost of applied `spend` effects (§11.2: amount × the
      // price in force at this point in the log, default 1). Other applied
      // verbs have no folded component in §2's nine keys.
      const applied = Array.isArray(body.applied) ? body.applied : [];
      for (const req of applied) {
        const r = asObject(req as Json);
        if (!r || !Array.isArray(r.args)) continue;
        const args = r.args as Json[];
        if (r.verb === "write" && typeof args[0] === "string") {
          state.units[args[0]] = args[1];
        } else if (
          r.verb === "spend" &&
          typeof args[0] === "string" &&
          typeof args[1] === "number" &&
          typeof body.producer === "string"
        ) {
          const posted = state.prices[args[0]];
          const price = typeof posted === "number" ? posted : 1;
          const current = state.budgets[body.producer];
          const balance = typeof current === "number" ? current : 0;
          state.budgets[body.producer] = balance - args[1] * price;
        }
      }
      break;
    }

    case "sense": {
      // §2 / §11.3: the latest published reading per sense name. The stored
      // value is the entry body's `value` verbatim (GAPS.md #8; caught by
      // checks c and f — the whole-body and {value:...} wrappings disagree
      // with both fixtures).
      if (typeof body.name === "string" && "value" in body) {
        state.senses[body.name] = body.value;
      }
      break;
    }

    case "checkpoint":
      // A checkpoint records a state hash; it does not change the state.
      break;

    case "machine": {
      // §2 / §10: machine definitions by name, as a list of version
      // wrappers holding the stored (parsed) machine.
      const machine = asObject(body.machine as Json);
      if (machine && typeof machine.name === "string") {
        appendWrapper(state.machines, machine.name, entry, body.machine as Json);
      }
      break;
    }

    case "transition": {
      // §10.3 + §2.1 (as amended after GAPS.md #9): the folded value
      // per instance is the OBJECT {"machine", "state"}, moved to
      // the entry's `to` on outcomes created/taken only.
      if (
        (body.outcome === "created" || body.outcome === "taken") &&
        typeof body.instance === "string" &&
        typeof body.to === "string"
      ) {
        state.machine_instances[body.instance] = {
          machine: body.machine as Json,
          state: body.to,
        };
      }
      break;
    }

    case "budget": {
      // §11.2: the folded balance is the sum of grants/deltas for the
      // producer (spend deductions happen under execution). The body's
      // field names are not stated in the spec (GAPS.md #10); we read
      // `producer` and `delta`.
      if (typeof body.producer === "string" && typeof body.delta === "number") {
        const current = state.budgets[body.producer];
        const balance = typeof current === "number" ? current : 0;
        state.budgets[body.producer] = balance + body.delta;
      }
      break;
    }

    case "price": {
      // §11.2: the posted price per resource. Field names are not stated
      // (GAPS.md #10); we read `resource` and `price`.
      if (typeof body.resource === "string" && typeof body.price === "number") {
        state.prices[body.resource] = body.price;
      }
      break;
    }

    case "rule": {
      // §2.1 (as amended after GAPS.md #11): the body is
      // {"producer", "rule"} and the folded value per rule id is
      // the `rule` object itself; a rule's stage is a
      // machine-instance state, never stored here.
      const rule = asObject(body.rule as Json);
      if (rule && typeof rule.rule_id === "string") {
        state.rules[rule.rule_id] = rule as Json;
      }
      break;
    }

    case "import": {
      // §2.1 (as amended after GAPS.md #12): an import entry has
      // NO fold effect. Imported configuration is applied by a
      // separate execution entry (§14).
      break;
    }

    default:
      // Unknown kinds change nothing; rejecting them is a validation
      // concern, not a fold concern. The spec does not say (GAPS.md #13).
      break;
  }
}

// Fold a whole log (or a prefix) into its folded state.
export function fold(entries: StoredEntry[]): FoldedState {
  const state = emptyState();
  for (const e of entries) applyEntry(state, e);
  return state;
}

// §2: the state hash is the §1 canonical hash of an object with exactly the
// nine named keys.
export function stateHash(state: FoldedState): string {
  return hash({
    units: state.units,
    senses: state.senses,
    dictionary: state.dictionary,
    decision_queue: state.decision_queue,
    machines: state.machines,
    machine_instances: state.machine_instances,
    budgets: state.budgets,
    prices: state.prices,
    rules: state.rules,
  });
}

export function foldStateHash(entries: StoredEntry[]): string {
  return stateHash(fold(entries));
}
