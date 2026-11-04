// Jacquard — TypeScript port of the reference kernel, Phase 7 slice 19.
//
// This file is a PORT, not a clean-room reimplementation. The
// Python source in src/jacquard/ is the reference behaviour and
// spec/SPEC.md is the contract; the code below mirrors, module
// by module: canonical helpers (via ./jacquard.ts), primitives.py,
// records.py, dictionary.py, policy.py, sequencer.py (sections 7
// and 7.1 — a kernel WITHOUT the lifecycle machines installed,
// which per spec section 10.4 behaves exactly as the 0.1 kernel:
// every lifecycle step in the Python reference is a no-op under
// that configuration), senses.py (section 11.3), the section
// 12.1 shape signature from learner.py, and the section 15.5
// anchor verifier from anchor.py.
//
// Node builtins only. Erasable TypeScript syntax only, so Node
// v24 runs this file with native type stripping.

import {
  createHash,
  createPrivateKey,
  createPublicKey,
  verify as cryptoVerify,
} from "node:crypto";

import {
  SPEC_VERSION,
  canonical,
  canonicalBytes,
  entryHash,
  fold,
  hash,
  makeEntry,
  stateHash,
  type FoldedState,
  type Json,
  type JsonObject,
  type StoredEntry,
} from "./jacquard.ts";

// ---------------------------------------------------------------------------
// Shared helpers: Python semantics the port must reproduce exactly.
// ---------------------------------------------------------------------------

export class Refusal extends Error {
  name: string;
  detail: string;
  constructor(name: string, detail: string) {
    super(`${name}: ${detail}`);
    this.name = name;
    this.detail = detail;
  }
}

export function deepClone<T>(value: T): T {
  return value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T);
}

function isObj(v: unknown): v is JsonObject {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// Python repr() for the value shapes that appear in refusal details.
export function pyRepr(v: unknown): string {
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") {
    return (
      "'" +
      v
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'")
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t") +
      "'"
    );
  }
  if (Array.isArray(v)) return "[" + v.map((x) => pyRepr(x)).join(", ") + "]";
  if (isObj(v)) {
    return (
      "{" +
      Object.entries(v)
        .map(([k, x]) => `${pyRepr(k)}: ${pyRepr(x)}`)
        .join(", ") +
      "}"
    );
  }
  return String(v);
}

// Python truthiness over canonical values (empty list/map are falsy).
export function pyTruthy(v: unknown): boolean {
  if (v === null || v === undefined || v === false) return false;
  if (v === true) return true;
  if (typeof v === "number") return v !== 0;
  if (typeof v === "string") return v.length > 0;
  if (Array.isArray(v)) return v.length > 0;
  if (isObj(v)) return Object.keys(v).length > 0;
  return Boolean(v);
}

// Python == over canonical values (True == 1, deep containers).
export function pyEq(a: unknown, b: unknown): boolean {
  const num = (x: unknown): number | null =>
    typeof x === "boolean" ? (x ? 1 : 0) : typeof x === "number" ? x : null;
  const na = num(a);
  const nb = num(b);
  if (na !== null || nb !== null) return na !== null && nb !== null && na === nb;
  if (a === null || b === null) return a === b;
  if (typeof a === "string" || typeof b === "string") return a === b;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => pyEq(x, b[i]));
  }
  if (isObj(a) && isObj(b)) {
    const ka = Object.keys(a);
    const kb = Object.keys(b);
    return (
      ka.length === kb.length &&
      ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && pyEq(a[k], b[k]))
    );
  }
  return false;
}

function pyCompare(a: unknown, b: unknown): number {
  const num = (x: unknown): number | null =>
    typeof x === "boolean" ? (x ? 1 : 0) : typeof x === "number" ? x : null;
  const na = num(a);
  const nb = num(b);
  if (na !== null && nb !== null) return na < nb ? -1 : na > nb ? 1 : 0;
  if (typeof a === "string" && typeof b === "string") {
    return a < b ? -1 : a > b ? 1 : 0;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    const n = Math.min(a.length, b.length);
    for (let i = 0; i < n; i++) {
      const c = pyCompare(a[i], b[i]);
      if (c !== 0) return c;
    }
    return a.length - b.length;
  }
  throw new Refusal("FIELD", `unorderable values: ${pyRepr(a)} vs ${pyRepr(b)}`);
}

// Lexicographic by Unicode code point (as in jacquard.ts).
export function compareCodePoints(a: string, b: string): number {
  const ac = Array.from(a);
  const bc = Array.from(b);
  const n = Math.min(ac.length, bc.length);
  for (let i = 0; i < n; i++) {
    const d = (ac[i].codePointAt(0) as number) - (bc[i].codePointAt(0) as number);
    if (d !== 0) return d;
  }
  return ac.length - bc.length;
}

function sortStrings(values: string[]): string[] {
  return [...values].sort(compareCodePoints);
}

function intChecked(value: unknown, what: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new Refusal("FIELD", `${what} expects an integer, got ${pyRepr(value)}`);
  }
  return value;
}

// ---------------------------------------------------------------------------
// primitives.py — the 26 primitives, syntax forms, evaluation context.
// ---------------------------------------------------------------------------

interface PrimSpec {
  tier: "P" | "E";
  ins: string[];
  outs: string[];
}

const TIER_P: { [name: string]: [string[], string[]] } = {
  self: [[], ["str"]],
  now: [[], ["int"]],
  get: [["str"], ["val"]],
  keys: [["str"], ["list"]],
  cands: [["str"], ["list"]],
  age: [["int"], ["int"]],
  record: [["str", "str"], ["map"]],
  sense: [["str"], ["val"]],
  similar: [["str", "int"], ["list"]],
  history: [["str", "int"], ["list"]],
  eq: [["val", "val"], ["bool"]],
  lt: [["val", "val"], ["bool"]],
  gt: [["val", "val"], ["bool"]],
  and: [["bool", "bool"], ["bool"]],
  or: [["bool", "bool"], ["bool"]],
  not: [["bool"], ["bool"]],
  add: [["int", "int"], ["int"]],
  sub: [["int", "int"], ["int"]],
  mul: [["int", "int"], ["int"]],
  div: [["int", "int"], ["int"]],
  mod: [["int", "int"], ["int"]],
  neg: [["int"], ["int"]],
  abs: [["int"], ["int"]],
  min2: [["int", "int"], ["int"]],
  max2: [["int", "int"], ["int"]],
  count: [["list"], ["int"]],
  sum: [["list"], ["int"]],
  min: [["list"], ["val"]],
  max: [["list"], ["val"]],
  contains: [["list", "val"], ["bool"]],
  hash: [["val"], ["str"]],
  verify: [["val", "str"], ["bool"]],
  evidence: [["int"], ["list"]],
  def: [["str"], ["map"]],
};

export const TIER_E: { [name: string]: [string[], string[]] } = {
  write: [["str", "val"], []],
  dispatch: [["map"], []],
  spend: [["str", "int"], []],
  notify: [["str", "val"], []],
  send: [["str", "val"], []],
  schedule: [["int", "map"], []],
  define: [["map"], []],
  checkpoint: [["str"], []],
};

export const PRIMITIVES: { [name: string]: PrimSpec } = {};
for (const [name, [ins, outs]] of Object.entries(TIER_P)) {
  PRIMITIVES[name] = { tier: "P", ins, outs };
}
for (const [name, [ins, outs]] of Object.entries(TIER_E)) {
  PRIMITIVES[name] = { tier: "E", ins, outs };
}

export const SYNTAX_FORMS = new Set([
  "dup", "drop", "swap", "over", "snoc", "assoc", "getf", "first", "cat",
]);

export type RecordLookup = (
  producer: string,
  cls: string,
) => { [key: string]: Json };

export class EvalContext {
  state: FoldedState;
  entries: StoredEntry[];
  producer: string;
  tentative: { [unit: string]: Json[] };
  recordLookup: RecordLookup | null;
  constructor(
    state: FoldedState,
    entries: StoredEntry[],
    producer: string,
    tentative: { [unit: string]: Json[] } = {},
    recordLookup: RecordLookup | null = null,
  ) {
    this.state = state;
    this.entries = entries;
    this.producer = producer;
    this.tentative = tentative;
    this.recordLookup = recordLookup;
  }
  get nowSeq(): number {
    return this.entries.length;
  }
}

// records.py — producer records projection.
export function projectRecords(entries: StoredEntry[]): {
  [producer: string]: { [cls: string]: { [k: string]: number } };
} {
  const out: {
    [producer: string]: { [cls: string]: { [k: string]: number } };
  } = {};
  const bucket = (producer: string, cls: string) => {
    const byCls = (out[producer] ??= {});
    return (byCls[cls] ??= {
      submissions: 0, allowed: 0, denied: 0, queued: 0, faults: 0,
      executions: 0,
    });
  };
  for (const entry of entries) {
    const body = entry.body;
    const producer = body.producer;
    if (typeof producer !== "string") continue;
    if (entry.kind === "definition") {
      const b = bucket(producer, "definition");
      b.submissions += 1;
      b.allowed += 1;
    } else if (entry.kind === "decision") {
      const b = bucket(producer, (body.class as string) ?? "work");
      b.submissions += 1;
      if (body.outcome === "allow") b.allowed += 1;
      else if (body.outcome === "deny") b.denied += 1;
      else if (body.outcome === "queued") b.queued += 1;
      if (body.fault) b.faults += 1;
    } else if (entry.kind === "execution") {
      const b = bucket(producer, (body.class as string) ?? "work");
      b.executions += 1;
    }
  }
  return out;
}

export function outputsAndUses(
  entries: StoredEntry[],
  producer: string,
): [number, number] {
  const produced = new Set<string>();
  for (const entry of entries) {
    if (entry.kind !== "execution") continue;
    if (entry.body.producer !== producer) continue;
    const applied = Array.isArray(entry.body.applied) ? entry.body.applied : [];
    for (const item of applied) {
      if (isObj(item) && Array.isArray(item.outputs)) {
        for (const o of item.outputs) produced.add(o as string);
      }
    }
  }
  const used = new Set<string>();
  for (const entry of entries) {
    if (entry.kind !== "execution") continue;
    const uses = Array.isArray(entry.body.uses) ? entry.body.uses : [];
    for (const u of uses) if (produced.has(u as string)) used.add(u as string);
  }
  return [produced.size, used.size];
}

function shapeKey(cls: string, effects: string[]): string {
  return `${cls}|${sortStrings(effects).join(",")}`;
}

function similarImpl(ctx: EvalContext, shape: Json, kRaw: Json): Json {
  const matches: Json[] = [];
  for (const entry of ctx.entries) {
    if (entry.kind !== "decision") continue;
    const body = entry.body;
    if (body.producer !== ctx.producer) continue;
    const cls = (body.class as string) ?? "work";
    const effects = Array.isArray(body.effects) ? (body.effects as string[]) : [];
    if (shapeKey(cls, effects) !== shape) continue;
    matches.push({
      class: cls,
      effects: body.effects ?? [],
      outcome: (body.outcome ?? null) as Json,
    });
  }
  const k = intChecked(kRaw, "similar");
  return k > 0 ? matches.slice(-k) : [];
}

function historyImpl(ctx: EvalContext, unit: Json, windowRaw: Json): Json {
  const values: Json[] = [];
  for (const entry of ctx.entries) {
    if (entry.kind !== "execution") continue;
    const applied = Array.isArray(entry.body.applied) ? entry.body.applied : [];
    for (const item of applied) {
      if (
        isObj(item) &&
        item.verb === "write" &&
        Array.isArray(item.args) &&
        item.args[0] === unit
      ) {
        values.push(item.args[1]);
      }
    }
  }
  const window = intChecked(windowRaw, "history");
  if (window >= 0) return window ? values.slice(-window) : [];
  return values;
}

function divmodPy(aRaw: Json, bRaw: Json): [number, number] {
  const a = intChecked(aRaw, "div/mod");
  const b = intChecked(bRaw, "div/mod");
  if (b === 0) throw new Refusal("FIELD", "division by zero");
  const q = Math.floor(a / b);
  return [q, a - q * b];
}

const has = (o: JsonObject, k: string): boolean =>
  Object.prototype.hasOwnProperty.call(o, k);

const IMPLS: { [name: string]: (ctx: EvalContext, ...args: Json[]) => Json } = {
  self: (ctx) => ctx.producer,
  now: (ctx) => ctx.nowSeq,
  get: (ctx, unit) =>
    has(ctx.state.units, unit as string) ? ctx.state.units[unit as string] : null,
  keys: (ctx, prefix) =>
    sortStrings(
      Object.keys(ctx.state.units).filter((k) =>
        k.startsWith(prefix as string),
      ),
    ) as Json,
  cands: (ctx, unit) => [...(ctx.tentative[unit as string] ?? [])] as Json,
  age: (ctx, seq) => Math.max(0, ctx.nowSeq - intChecked(seq, "age")),
  record: (ctx, producer, cls) =>
    ctx.recordLookup
      ? (ctx.recordLookup(producer as string, cls as string) as Json)
      : {},
  sense: (ctx, name) =>
    has(ctx.state.senses, name as string)
      ? ctx.state.senses[name as string]
      : null,
  similar: (ctx, shape, k) => similarImpl(ctx, shape, k),
  history: (ctx, unit, window) => historyImpl(ctx, unit, window),
  eq: (_ctx, a, b) => pyEq(a, b),
  lt: (_ctx, a, b) => pyCompare(a, b) < 0,
  gt: (_ctx, a, b) => pyCompare(a, b) > 0,
  and: (_ctx, a, b) => pyTruthy(a) && pyTruthy(b),
  or: (_ctx, a, b) => pyTruthy(a) || pyTruthy(b),
  not: (_ctx, a) => !pyTruthy(a),
  add: (_ctx, a, b) => intChecked(a, "add") + intChecked(b, "add"),
  sub: (_ctx, a, b) => intChecked(a, "sub") - intChecked(b, "sub"),
  mul: (_ctx, a, b) => intChecked(a, "mul") * intChecked(b, "mul"),
  div: (_ctx, a, b) => divmodPy(a, b)[0],
  mod: (_ctx, a, b) => divmodPy(a, b)[1],
  neg: (_ctx, a) => -intChecked(a, "neg"),
  abs: (_ctx, a) => Math.abs(intChecked(a, "abs")),
  min2: (_ctx, a, b) => Math.min(intChecked(a, "min2"), intChecked(b, "min2")),
  max2: (_ctx, a, b) => Math.max(intChecked(a, "max2"), intChecked(b, "max2")),
  count: (_ctx, xs) => (xs as Json[]).length,
  sum: (_ctx, xs) =>
    (xs as Json[]).reduce<number>((acc, x) => acc + intChecked(x, "sum"), 0),
  min: (_ctx, xs) => {
    const list = xs as Json[];
    if (!list.length) return null;
    return list.reduce((m, x) => (pyCompare(x, m) < 0 ? x : m));
  },
  max: (_ctx, xs) => {
    const list = xs as Json[];
    if (!list.length) return null;
    return list.reduce((m, x) => (pyCompare(x, m) > 0 ? x : m));
  },
  contains: (_ctx, xs, x) => (xs as Json[]).some((item) => pyEq(item, x)),
  hash: (_ctx, value) => hash(value),
  verify: (_ctx, value, digest) => hash(value) === digest,
  evidence: (ctx, seqRaw) => {
    const seq = intChecked(seqRaw, "evidence");
    if (0 <= seq && seq < ctx.entries.length) {
      const ev = ctx.entries[seq].body.evidence;
      return (Array.isArray(ev) ? ev : []) as Json;
    }
    return [];
  },
  def: (ctx, name) => {
    const versions = ctx.state.dictionary[name as string];
    return versions && versions.length
      ? (deepClone(versions[versions.length - 1].definition) as Json)
      : {};
  },
};

// ---------------------------------------------------------------------------
// dictionary.py — definitions and the dictionary (spec section 5).
// ---------------------------------------------------------------------------

const TYPES = ["val", "int", "bool", "str", "list", "map"];

function typeOf(value: unknown): string {
  if (typeof value === "boolean") return "bool";
  if (typeof value === "number" && Number.isInteger(value)) return "int";
  if (typeof value === "string") return "str";
  if (Array.isArray(value)) return "list";
  if (isObj(value)) return "map";
  return "val";
}

function unify(a: string, b: string): string | null {
  if (a === b) return a;
  if (a === "val") return b;
  if (b === "val") return a;
  return null;
}

function formKey(token: JsonObject): string {
  const keys = sortStrings(Object.keys(token));
  return keys.length ? keys[0] : "";
}

function isLitToken(token: unknown): token is JsonObject {
  return isObj(token) && Object.keys(token).length === 1 && has(token, "lit");
}

function isIfToken(token: unknown): token is JsonObject {
  return (
    isObj(token) &&
    has(token, "if") &&
    Object.keys(token).every((k) => k === "if" || k === "else")
  );
}

// The form-agnostic effects walk (spec section 5): descend into
// every token position of every form except a literal's value.
export function* walkTokens(tokens: Json[]): Generator<Json> {
  for (const token of tokens) {
    yield token;
    if (isObj(token)) {
      for (const [key, value] of Object.entries(token)) {
        if (key === "lit" && Object.keys(token).length === 1) continue;
        if (Array.isArray(value)) yield* walkTokens(value as Json[]);
      }
    } else if (Array.isArray(token)) {
      yield* walkTokens(token as Json[]);
    }
  }
}

interface Resolved {
  kind: "primitive" | "word";
  ins: string[];
  outs: string[];
  entryHash: string | null;
  definition: JsonObject | null;
}

export type StoredDefinition = JsonObject;

export class Dictionary {
  state: FoldedState;
  getEntries: () => StoredEntry[];
  getTentative: () => { [unit: string]: Json[] };
  recordLookup: RecordLookup | null;

  constructor(
    state: FoldedState,
    getEntries: () => StoredEntry[],
    getTentative?: () => { [unit: string]: Json[] },
    recordLookup?: RecordLookup | null,
  ) {
    this.state = state;
    this.getEntries = getEntries;
    this.getTentative = getTentative ?? (() => ({}));
    this.recordLookup = recordLookup ?? null;
  }

  resolve(name: string): Resolved | null {
    if (has(PRIMITIVES, name)) {
      const spec = PRIMITIVES[name];
      return {
        kind: "primitive", ins: spec.ins, outs: spec.outs,
        entryHash: null, definition: null,
      };
    }
    const versions = this.state.dictionary[name];
    if (versions && versions.length) {
      const latest = versions[versions.length - 1];
      const defn = latest.definition as JsonObject;
      const sig = defn.signature as JsonObject;
      return {
        kind: "word",
        ins: sig.ins as string[],
        outs: sig.outs as string[],
        entryHash: latest.entry_hash,
        definition: defn,
      };
    }
    return null;
  }

  versionByHash(name: string, entryHash: string): JsonObject | null {
    for (const version of this.state.dictionary[name] ?? []) {
      if (version.entry_hash === entryHash) {
        return version.definition as JsonObject;
      }
    }
    return null;
  }

  computedEffects(defn: JsonObject, seenArg?: Set<string>): Set<string> {
    const effects = new Set<string>();
    const seen = seenArg ?? new Set<string>();
    for (const token of walkTokens(defn.body as Json[])) {
      if (typeof token !== "string") continue;
      if (has(TIER_E, token)) {
        effects.add(token);
      } else if (!has(PRIMITIVES, token) && !SYNTAX_FORMS.has(token)) {
        const resolved = this.resolve(token);
        if (resolved && resolved.kind === "word") {
          const key = resolved.entryHash as string;
          if (!seen.has(key)) {
            seen.add(key);
            for (const e of this.computedEffects(
              resolved.definition as JsonObject,
              seen,
            )) {
              effects.add(e);
            }
          }
        }
      }
    }
    return effects;
  }

  define(defn: JsonObject): StoredDefinition {
    for (const field of ["name", "signature", "body", "examples"]) {
      if (!has(defn, field)) {
        throw new Refusal("FIELD", `definition missing field: ${field}`);
      }
    }
    const sig = defn.signature as JsonObject;
    if (!has(sig, "ins") || !has(sig, "outs")) {
      throw new Refusal("FIELD", "signature needs ins and outs");
    }
    for (const t of [...(sig.ins as string[]), ...(sig.outs as string[])]) {
      if (!TYPES.includes(t)) {
        throw new Refusal("FIELD", `unknown type in signature: ${pyRepr(t)}`);
      }
    }
    const refs: { [name: string]: string } = {};
    for (const token of walkTokens(defn.body as Json[])) {
      if (
        typeof token === "string" &&
        !has(PRIMITIVES, token) &&
        !SYNTAX_FORMS.has(token)
      ) {
        const resolved = this.resolve(token);
        if (resolved === null || resolved.kind !== "word") {
          throw new Refusal("SPEC", `unknown reference: ${token}`);
        }
        refs[token] = resolved.entryHash as string;
      }
    }
    this.checkSignature(defn);
    const effects = this.computedEffects(defn);
    const declared = defn.declared_effects;
    if (declared !== undefined && declared !== null) {
      const declaredSet = new Set(declared as string[]);
      if (
        declaredSet.size !== effects.size ||
        ![...declaredSet].every((e) => effects.has(e))
      ) {
        throw new Refusal(
          "UNDERDECLARED",
          `declared effects ${pyRepr(sortStrings([...declaredSet]))} do not equal computed effects ${pyRepr(sortStrings([...effects]))}`,
        );
      }
    }
    this.checkExamples(defn);
    return {
      name: defn.name,
      signature: defn.signature,
      body: defn.body,
      examples: defn.examples,
      refs,
      computed_effects: sortStrings([...effects]),
    };
  }

  // ---- signature simulation ----
  simulate(tokens: Json[], stack: string[], defnName: string): string[] {
    for (const token of tokens) {
      if (isLitToken(token)) {
        stack.push(typeOf(token.lit));
      } else if (isIfToken(token)) {
        if (!stack.length) {
          throw new Refusal("FIELD", `${defnName}: if with empty stack`);
        }
        const cond = stack.pop() as string;
        if (unify(cond, "bool") === null) {
          throw new Refusal(
            "FIELD",
            `${defnName}: if condition is ${cond}, not bool`,
          );
        }
        const thenStack = this.simulate(
          (token.if as Json[]) ?? [], [...stack], defnName,
        );
        const elseStack = this.simulate(
          (token.else as Json[]) ?? [], [...stack], defnName,
        );
        if (
          thenStack.length !== elseStack.length ||
          thenStack.some((a, i) => unify(a, elseStack[i]) === null)
        ) {
          throw new Refusal(
            "FIELD",
            `${defnName}: if branches leave different stack shapes (${pyRepr(thenStack)} vs ${pyRepr(elseStack)})`,
          );
        }
        stack.length = 0;
        stack.push(...thenStack);
      } else if (isObj(token)) {
        throw new Refusal(
          "SPEC",
          `${defnName}: token form ${pyRepr(formKey(token))} is not defined in this version (SPEC section 5)`,
        );
      } else if (typeof token === "string" && SYNTAX_FORMS.has(token)) {
        this.simulateSyntax(token, stack, defnName);
      } else if (typeof token === "string") {
        const resolved = this.resolve(token);
        if (resolved === null) {
          throw new Refusal("SPEC", `unknown reference: ${token}`);
        }
        const { ins, outs } = resolved;
        if (stack.length < ins.length) {
          throw new Refusal(
            "FIELD", `${defnName}: stack underflow at ${token}`,
          );
        }
        const args = stack.slice(stack.length - ins.length);
        stack.length = stack.length - ins.length;
        for (let i = 0; i < ins.length; i++) {
          if (unify(ins[i], args[i]) === null) {
            throw new Refusal(
              "FIELD",
              `${defnName}: ${token} expects ${pyRepr(ins)}, stack has ${pyRepr(args)}`,
            );
          }
        }
        stack.push(...outs);
      } else {
        throw new Refusal(
          "FIELD", `${defnName}: bad token ${pyRepr(token)}`,
        );
      }
    }
    return stack;
  }

  simulateSyntax(token: string, stack: string[], defnName: string): void {
    const need = (n: number) => {
      if (stack.length < n) {
        throw new Refusal(
          "FIELD", `${defnName}: stack underflow at ${token}`,
        );
      }
    };
    if (token === "dup") {
      need(1);
      stack.push(stack[stack.length - 1]);
    } else if (token === "drop") {
      need(1);
      stack.pop();
    } else if (token === "swap") {
      need(2);
      const a = stack[stack.length - 1];
      stack[stack.length - 1] = stack[stack.length - 2];
      stack[stack.length - 2] = a;
    } else if (token === "over") {
      need(2);
      stack.push(stack[stack.length - 2]);
    } else if (token === "snoc") {
      need(2);
      stack.pop();
      const xs = stack.pop() as string;
      if (unify(xs, "list") === null) {
        throw new Refusal("FIELD", `${defnName}: snoc on ${xs}`);
      }
      stack.push("list");
    } else if (token === "assoc") {
      need(3);
      stack.pop();
      const key = stack.pop() as string;
      const m = stack.pop() as string;
      if (unify(m, "map") === null || unify(key, "str") === null) {
        throw new Refusal("FIELD", `${defnName}: assoc on ${m}/${key}`);
      }
      stack.push("map");
    } else if (token === "getf") {
      need(2);
      const key = stack.pop() as string;
      const m = stack.pop() as string;
      if (unify(m, "map") === null || unify(key, "str") === null) {
        throw new Refusal("FIELD", `${defnName}: getf on ${m}/${key}`);
      }
      stack.push("val");
    } else if (token === "first") {
      need(1);
      const xs = stack.pop() as string;
      if (unify(xs, "list") === null) {
        throw new Refusal("FIELD", `${defnName}: first on ${xs}`);
      }
      stack.push("val");
    } else if (token === "cat") {
      need(2);
      const b = stack.pop() as string;
      const a = stack.pop() as string;
      if (unify(a, "str") === null || unify(b, "str") === null) {
        throw new Refusal("FIELD", `${defnName}: cat on ${a}/${b}`);
      }
      stack.push("str");
    }
  }

  checkSignature(defn: JsonObject): void {
    const sig = defn.signature as JsonObject;
    const stack = [...(sig.ins as string[])];
    const result = this.simulate(defn.body as Json[], stack, defn.name as string);
    const outs = sig.outs as string[];
    if (
      result.length !== outs.length ||
      result.some((a, i) => unify(a, outs[i]) === null)
    ) {
      throw new Refusal(
        "FIELD",
        `${defn.name as string}: body leaves stack ${pyRepr(result)}, signature promises ${pyRepr(outs)}`,
      );
    }
  }

  // ---- examples ----
  checkExamples(defn: JsonObject): void {
    const examples = (defn.examples as JsonObject[] | undefined) ?? [];
    examples.forEach((example, i) => {
      const state: FoldedState = {
        units: {}, senses: {}, dictionary: {}, decision_queue: {},
        machines: {}, machine_instances: {}, budgets: {}, prices: {},
        rules: {},
      };
      const given = (example.state as JsonObject | undefined) ?? {};
      Object.assign(state.units, deepClone(given.units ?? {}));
      Object.assign(state.senses, deepClone(given.senses ?? {}));
      const ctx = new EvalContext(
        state, this.getEntries(), "example", this.getTentative(),
        this.recordLookup,
      );
      const refs: { [name: string]: string } = {};
      for (const token of walkTokens(defn.body as Json[])) {
        if (
          typeof token === "string" &&
          !has(PRIMITIVES, token) &&
          !SYNTAX_FORMS.has(token)
        ) {
          const resolved = this.resolve(token);
          if (resolved && resolved.kind === "word") {
            refs[token] = resolved.entryHash as string;
          }
        }
      }
      let stack: Json[];
      let requests: JsonObject[];
      try {
        [stack, requests] = this.run(
          defn.body as Json[],
          deepClone((example.args as Json[] | undefined) ?? []),
          ctx,
          refs,
        );
      } catch (err) {
        if (err instanceof Refusal) {
          throw new Refusal(
            "EXAMPLE", `example ${i}: evaluation refused: ${err.detail}`,
          );
        }
        throw err;
      }
      if (has(example, "expect") && !pyEq(stack, example.expect)) {
        throw new Refusal(
          "EXAMPLE",
          `example ${i}: expected final stack ${pyRepr(example.expect)}, got ${pyRepr(stack)}`,
        );
      }
      if (has(example, "requests")) {
        const verbs = requests.map((r) => r.verb);
        if (!pyEq(verbs, example.requests)) {
          throw new Refusal(
            "EXAMPLE",
            `example ${i}: expected requests ${pyRepr(example.requests)}, got ${pyRepr(verbs)}`,
          );
        }
      }
    });
  }

  // ---- evaluation ----
  evaluate(
    name: string, args: Json[], ctx: EvalContext,
  ): [Json[], JsonObject[]] {
    const versions = this.state.dictionary[name];
    if (!versions || !versions.length) {
      throw new Refusal("SPEC", `no such definition: ${name}`);
    }
    const defn = versions[versions.length - 1].definition as JsonObject;
    return this.run(
      defn.body as Json[], [...args], ctx,
      (defn.refs as { [n: string]: string } | undefined) ?? {},
    );
  }

  run(
    tokens: Json[], stack: Json[], ctx: EvalContext,
    refs: { [name: string]: string },
  ): [Json[], JsonObject[]] {
    const requests: JsonObject[] = [];
    this.exec(tokens, stack, requests, ctx, refs);
    return [stack, requests];
  }

  exec(
    tokens: Json[], stack: Json[], requests: JsonObject[],
    ctx: EvalContext, refs: { [name: string]: string },
  ): void {
    for (const token of tokens) {
      if (isLitToken(token)) {
        stack.push(deepClone(token.lit));
      } else if (isIfToken(token)) {
        if (!stack.length) throw new Refusal("FIELD", "if with empty stack");
        const branch = pyTruthy(stack.pop())
          ? ((token.if as Json[]) ?? [])
          : ((token.else as Json[]) ?? []);
        this.exec(branch, stack, requests, ctx, refs);
      } else if (typeof token === "string" && SYNTAX_FORMS.has(token)) {
        this.execSyntax(token, stack);
      } else if (typeof token === "string" && has(PRIMITIVES, token)) {
        const spec = PRIMITIVES[token];
        const n = spec.ins.length;
        if (stack.length < n) {
          throw new Refusal("FIELD", `stack underflow at ${token}`);
        }
        const args = stack.slice(stack.length - n);
        stack.length = stack.length - n;
        if (spec.tier === "E") {
          requests.push({ verb: token, args: deepClone(args) as Json });
        } else {
          stack.push(IMPLS[token](ctx, ...args));
        }
      } else if (typeof token === "string") {
        let defn: JsonObject | null = null;
        if (has(refs, token)) {
          defn = this.versionByHash(token, refs[token]);
        }
        if (defn === null) {
          const versions = this.state.dictionary[token];
          if (versions && versions.length) {
            defn = versions[versions.length - 1].definition as JsonObject;
          }
        }
        if (defn === null) {
          throw new Refusal("SPEC", `unknown reference: ${token}`);
        }
        this.exec(
          defn.body as Json[], stack, requests, ctx,
          (defn.refs as { [n: string]: string } | undefined) ?? {},
        );
      } else if (isObj(token)) {
        throw new Refusal(
          "SPEC",
          `token form ${pyRepr(formKey(token))} is not defined in this version (SPEC section 5)`,
        );
      } else {
        throw new Refusal("FIELD", `bad token ${pyRepr(token)}`);
      }
    }
  }

  execSyntax(token: string, stack: Json[]): void {
    const need = (n: number) => {
      if (stack.length < n) {
        throw new Refusal("FIELD", `stack underflow at ${token}`);
      }
    };
    if (token === "dup") {
      need(1);
      stack.push(stack[stack.length - 1]);
    } else if (token === "drop") {
      need(1);
      stack.pop();
    } else if (token === "swap") {
      need(2);
      const a = stack[stack.length - 1];
      stack[stack.length - 1] = stack[stack.length - 2];
      stack[stack.length - 2] = a;
    } else if (token === "over") {
      need(2);
      stack.push(stack[stack.length - 2]);
    } else if (token === "snoc") {
      need(2);
      const value = stack.pop() as Json;
      const xs = stack.pop() as Json[];
      stack.push([...xs, value]);
    } else if (token === "assoc") {
      need(3);
      const value = stack.pop() as Json;
      const key = stack.pop() as string;
      const m = stack.pop() as JsonObject;
      stack.push({ ...m, [key]: value });
    } else if (token === "getf") {
      need(2);
      const key = stack.pop() as string;
      const m = stack.pop() as JsonObject;
      stack.push(has(m, key) ? m[key] : null);
    } else if (token === "first") {
      need(1);
      const xs = stack.pop() as Json[];
      if (!xs.length) throw new Refusal("FIELD", "first of empty list");
      stack.push(xs[0]);
    } else if (token === "cat") {
      need(2);
      const b = stack.pop() as string;
      const a = stack.pop() as string;
      stack.push(a + b);
    }
  }
}

// ---------------------------------------------------------------------------
// policy.py — the policy gate (spec section 7), policy/1.
// ---------------------------------------------------------------------------

export const POLICY_VERSION = "policy/1";
const PROTECTED_EFFECTS = ["send", "notify", "spend", "irreversible"];

export function decidePolicy(
  producer: string,
  _kind: string,
  effects: Set<string>,
  _recordView: unknown,
  standing: JsonObject | null | undefined,
): ["allow" | "deny" | "queue", string[]] {
  if (standing && standing.status === "suspended") {
    return ["deny", ["producer-suspended"]];
  }
  const protectedList = sortStrings(
    [...effects].filter((e) => PROTECTED_EFFECTS.includes(e)),
  );
  if (protectedList.length && producer !== "operator") {
    return ["queue", protectedList.map((v) => `protected-effect:${v}`)];
  }
  return ["allow", []];
}

// ---------------------------------------------------------------------------
// envelope.py — envelope validation (spec section 3), Python order.
// ---------------------------------------------------------------------------

import { SPEC_SEAL, GENESIS_PREV } from "./jacquard.ts";

const ENVELOPE_FIELDS = [
  "v", "id", "producer", "kind", "body", "declared_effects", "spec_seal",
];

export function envelopeHash(env: JsonObject): string {
  return hash(env as Json);
}

export function validateEnvelopePy(
  envelope: unknown,
): [string, string] | null {
  if (!isObj(envelope)) return ["FIELD", "envelope is not an object"];
  for (const field of ENVELOPE_FIELDS) {
    if (!has(envelope, field)) {
      return ["FIELD", `envelope missing field: ${field}`];
    }
  }
  if (envelope.v !== 1) {
    return ["SPEC", `unsupported envelope version: ${pyRepr(envelope.v)}`];
  }
  if (envelope.spec_seal !== SPEC_SEAL) return ["SPEC", "spec seal mismatch"];
  if (!["proposal", "definition", "machine"].includes(envelope.kind as string)) {
    return ["FIELD", `unknown envelope kind: ${pyRepr(envelope.kind)}`];
  }
  if (!Array.isArray(envelope.declared_effects)) {
    return ["FIELD", "declared_effects must be a list"];
  }
  return null;
}

// ---------------------------------------------------------------------------
// log.py — the append-only hash-chained log (spec section 2).
// ---------------------------------------------------------------------------

export const ENTRY_KINDS = [
  "proposal", "decision", "definition", "execution", "sense",
  "checkpoint", "machine", "transition", "budget", "price", "rule",
  "import",
];

export class Log {
  entries: StoredEntry[];
  constructor(entries: StoredEntry[] = []) {
    this.entries = entries;
  }
  append(kind: string, body: JsonObject): StoredEntry {
    if (!ENTRY_KINDS.includes(kind)) {
      throw new Error(`unknown entry kind: ${pyRepr(kind)}`);
    }
    const prev = this.entries.length
      ? this.entries[this.entries.length - 1].hash
      : GENESIS_PREV;
    const entry = makeEntry(this.entries.length, prev, kind, deepClone(body));
    const stored: StoredEntry = { ...entry, hash: entryHash(entry) };
    this.entries.push(stored);
    return stored;
  }
  verifyChain(): boolean {
    return verifyInternalChain(this.entries);
  }
  // The on-disk form: one canonical line per entry, hash included.
  serialise(): string {
    return this.entries
      .map((e) => canonical(e as unknown as Json) + "\n")
      .join("");
  }
}

export function verifyInternalChain(entries: StoredEntry[]): boolean {
  let prev = GENESIS_PREV;
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e.seq !== i || e.prev !== prev) return false;
    const recomputed = entryHash(e);
    if (recomputed !== e.hash) return false;
    prev = e.hash;
  }
  return true;
}

// ---------------------------------------------------------------------------
// sequencer.py — the sequencer (spec sections 3, 7, 7.1).
//
// Lifecycle machines are not ported: this is a kernel without the
// lifecycle machines installed, so every _lifecycle / approval
// step of the Python reference is a no-op here, exactly as in a
// Python Sequencer whose machine registry is empty (spec 10.4).
// ---------------------------------------------------------------------------

export type Verdict = JsonObject;
type RuleDecider = (
  producer: string,
  cls: string,
  effects: Set<string>,
  outcome: string,
  reasons: string[],
  requests: Json[] | undefined,
) => [string, string] | null;

const OUTCOME_STORED: { [k: string]: string } = {
  allow: "allow", deny: "deny", queue: "queued",
};

export class Sequencer {
  log: Log;
  standing: { [producer: string]: JsonObject };
  tentative: { [unit: string]: Json[] };
  verdicts: { [envHash: string]: Verdict };
  pumping: boolean;
  ruleDecider: RuleDecider | null;
  state: FoldedState;
  dictionary: Dictionary;

  constructor(log?: Log, standing?: { [producer: string]: JsonObject }) {
    this.log = log ?? new Log();
    this.standing = standing ?? {};
    this.tentative = {};
    this.verdicts = {};
    this.pumping = false;
    this.ruleDecider = null;
    this.state = fold(this.log.entries);
    this.dictionary = new Dictionary(
      this.state,
      () => this.log.entries,
      () => this.tentative,
      (p, c) => this.recordLookup(p, c),
    );
    // SPEC 3.1: the verdict cache is rebuilt from the log, so
    // resubmission replays the recorded verdict in any
    // process, not just the one that decided it.
    this.verdicts = this.recordedVerdicts();
  }

  recordedVerdicts(): { [envHash: string]: Verdict } {
    const recorded: { [envHash: string]: Verdict } = {};
    for (const entry of this.log.entries) {
      const body = entry.body;
      if (entry.kind === "decision") {
        const pid = body.proposal_id as string | undefined;
        if (pid === undefined || has(recorded, pid)) continue;
        if (has(body, "releases") || has(body, "rejects")
            || has(body, "expires")) {
          continue;
        }
        if (body.outcome === "refused") {
          const reasons = (body.reasons as Json[] | undefined) ?? [];
          recorded[pid] = {
            status: "REFUSED", refusal: body.fault as string,
            detail: (reasons[0] as string) ?? "", proposal_id: pid,
          };
        } else {
          recorded[pid] = {
            status: "decided",
            outcome: body.outcome === "queued"
              ? "queue" : body.outcome as string,
            proposal_id: pid,
            reasons: deepClone(body.reasons ?? []) as Json,
          };
        }
      } else if (entry.kind === "definition" && has(body, "envelope")) {
        const envHash = body.envelope as string;
        if (has(recorded, envHash)) continue;
        recorded[envHash] = {
          status: "accepted", entry: entry.hash,
          computed_effects:
            (body.definition as JsonObject).computed_effects as Json,
        };
      }
      // Machine entries are not scanned: this port refuses
      // machine envelopes by scope (spec section 10), fresh
      // or replayed alike.
    }
    return recorded;
  }

  refold(): void {
    this.state = fold(this.log.entries);
    this.dictionary.state = this.state;
  }

  recordLookup(producer: string, cls: string): { [key: string]: Json } {
    const view = projectRecords(this.log.entries);
    return (view[producer]?.[cls] ?? {}) as { [key: string]: Json };
  }

  context(producer: string): EvalContext {
    return new EvalContext(
      this.state, this.log.entries, producer, this.tentative,
      (p, c) => this.recordLookup(p, c),
    );
  }

  evaluateWord(
    name: string, producer: string, args: Json[] = [],
  ): [Json[], JsonObject[]] {
    return this.dictionary.evaluate(name, [...args], this.context(producer));
  }

  setStanding(producer: string, standing: JsonObject): void {
    this.standing[producer] = standing;
  }

  // ---- senses / checkpoints / budgets / prices ----
  submitSense(name: string, value: Json, producer: string): StoredEntry {
    const entry = this.log.append("sense", { producer, name, value });
    this.refold();
    this.pumpWaits();
    return entry;
  }

  checkpoint(name: string): StoredEntry {
    const entry = this.log.append("checkpoint", {
      name, state_hash: stateHash(this.state),
    });
    this.refold();
    this.pumpWaits();
    return entry;
  }

  grantBudget(
    producer: string, amount: number, by = "operator",
  ): JsonObject {
    const entry = this.log.append("budget", {
      producer, delta: Math.trunc(amount), by,
    });
    this.refold();
    this.pumpWaits();
    return { entry: entry.hash, balance: this.state.budgets[producer] ?? 0 };
  }

  postPrice(resource: string, price: number, by = "operator"): JsonObject {
    const entry = this.log.append("price", {
      resource, price: Math.trunc(price), by,
    });
    this.refold();
    this.pumpWaits();
    return { entry: entry.hash, price: Math.trunc(price) };
  }

  // ---- submit ----
  submit(envelope: JsonObject): Verdict {
    const problem = validateEnvelopePy(envelope);
    if (problem !== null) {
      return { status: "REFUSED", refusal: problem[0], detail: problem[1] };
    }
    const envHash = envelopeHash(envelope);
    if (has(this.verdicts, envHash)) {
      const replay = deepClone(this.verdicts[envHash]);
      replay.duplicate = true;
      return replay;
    }
    let verdict: Verdict;
    if (envelope.kind === "definition") {
      verdict = this.submitDefinition(envelope, envHash);
    } else if (envelope.kind === "machine") {
      verdict = {
        status: "REFUSED", refusal: "SPEC",
        detail: "machine envelopes are outside the TS port's scope (spec section 10; the fold covers machine entries)",
      };
    } else {
      verdict = this.submitProposal(envelope, envHash);
    }
    this.verdicts[envHash] = deepClone(verdict);
    this.pumpWaits();
    return verdict;
  }

  submitDefinition(envelope: JsonObject, envHash: string): Verdict {
    let stored: StoredDefinition;
    try {
      stored = this.dictionary.define(envelope.body as JsonObject);
    } catch (err) {
      if (err instanceof Refusal) {
        return { status: "REFUSED", refusal: err.name, detail: err.detail };
      }
      throw err;
    }
    const entry = this.log.append("definition", {
      producer: envelope.producer, definition: stored,
      envelope: envHash,
    });
    this.refold();
    return {
      status: "accepted", entry: entry.hash,
      computed_effects: stored.computed_effects,
    };
  }

  checkRequests(requests: unknown): [string, string] | null {
    if (!Array.isArray(requests)) {
      return ["FIELD", "proposal body.requests must be a list"];
    }
    for (const request of requests) {
      if (!isObj(request) || !has(request, "verb") || !has(request, "args")) {
        return ["FIELD", "each request needs verb and args"];
      }
      if (!has(TIER_E, request.verb as string)) {
        return ["FIELD", `unknown effect verb: ${pyRepr(request.verb)}`];
      }
      if (request.verb === "write") {
        const args = request.args as Json[];
        if (!Array.isArray(args) || args.length !== 2 || typeof args[0] !== "string") {
          return ["FIELD", "write expects [unit, value]"];
        }
      }
    }
    return null;
  }

  waitPrecheck(
    wait: unknown, declaredEffects: Json[], body: JsonObject,
    requests: JsonObject[], envHash: string,
  ): Verdict | null {
    const badShape =
      !isObj(wait) ||
      typeof wait.guard !== "string" ||
      typeof wait.deadline_seq !== "number" ||
      !Number.isInteger(wait.deadline_seq);
    if (badShape) {
      return {
        status: "REFUSED", refusal: "FIELD",
        detail: 'wait must be {"guard": <word name>, "deadline_seq": <int>}',
        proposal_id: envHash,
      };
    }
    const w = wait as JsonObject;
    const guard = w.guard as string;
    const resolved = this.dictionary.resolve(guard);
    if (resolved === null || resolved.kind !== "word") {
      return {
        status: "REFUSED", refusal: "SPEC",
        detail: `wait guard is not a dictionary word: ${guard}`,
        proposal_id: envHash,
      };
    }
    const defn = resolved.definition as JsonObject;
    const effects = new Set((defn.computed_effects as string[]) ?? []);
    if (
      JSON.stringify(resolved.ins) !== JSON.stringify(["map"]) ||
      JSON.stringify(resolved.outs) !== JSON.stringify(["bool"])
    ) {
      return {
        status: "REFUSED", refusal: "FIELD",
        detail: `wait guard ${guard} must have signature (map -> bool), has (${pyRepr(resolved.ins)} -> ${pyRepr(resolved.outs)})`,
        proposal_id: envHash,
      };
    }
    if (effects.size) {
      return {
        status: "REFUSED", refusal: "SPEC",
        detail: `wait guard ${guard} must be pure, its computed effects are ${pyRepr(sortStrings([...effects]))}`,
        proposal_id: envHash,
      };
    }
    const actual = new Set<string>();
    for (const request of requests) actual.add(request.verb as string);
    if (body.irreversible) actual.add("irreversible");
    const declared = new Set(declaredEffects as string[]);
    if (![...actual].every((e) => declared.has(e))) {
      return {
        status: "REFUSED", refusal: "UNDERDECLARED",
        detail: `declared effects ${pyRepr(sortStrings([...declared]))} do not cover actual effects ${pyRepr(sortStrings([...actual]))}`,
        proposal_id: envHash,
      };
    }
    return null;
  }

  submitProposal(envelope: JsonObject, envHash: string): Verdict {
    const producer = envelope.producer as string;
    const body = envelope.body as JsonObject;
    const cls = (body.class as string | undefined) ?? "work";
    const requests = body.requests as JsonObject[] | undefined;
    const problem = this.checkRequests(requests);
    if (problem !== null) {
      return { status: "REFUSED", refusal: problem[0], detail: problem[1] };
    }
    const reqs = requests as JsonObject[];
    const wait = body.wait;
    let waitSatisfied: string | null = null;
    if (wait !== undefined && wait !== null) {
      const early = this.waitPrecheck(
        wait, envelope.declared_effects as Json[], body, reqs, envHash,
      );
      if (early !== null) return early;
      const guard = (wait as JsonObject).guard as string;
      let stack: Json[];
      let emitted: JsonObject[];
      try {
        [stack, emitted] = this.evaluateWord(guard, producer, [
          { proposal_id: envHash },
        ]);
      } catch (err) {
        if (err instanceof Refusal) {
          return {
            status: "REFUSED", refusal: err.name, detail: err.detail,
            proposal_id: envHash,
          };
        }
        throw err;
      }
      if (emitted.length) {
        return {
          status: "REFUSED", refusal: "SPEC",
          detail: `wait guard ${guard} emitted requests ${pyRepr(emitted)}`,
          proposal_id: envHash,
        };
      }
      if (pyEq(stack, [true])) {
        waitSatisfied = guard;
      } else if (pyEq(stack, [false])) {
        const effects = new Set<string>();
        for (const request of reqs) effects.add(request.verb as string);
        if (body.irreversible) effects.add("irreversible");
        this.log.append("decision", {
          producer, class: cls, proposal_id: envHash,
          policy_version: POLICY_VERSION, outcome: "queued",
          reasons: [`waiting:${guard}`], effects: sortStrings([...effects]),
          requests: reqs, irreversible: Boolean(body.irreversible ?? false),
          uses: body.uses ?? [], wait: deepClone(wait) as Json,
        });
        this.refold();
        return {
          status: "decided", outcome: "queue", proposal_id: envHash,
          reasons: [`waiting:${guard}`],
        };
      } else {
        return {
          status: "REFUSED", refusal: "FIELD",
          detail: `wait guard ${guard} must leave exactly one bool, got ${pyRepr(stack)}`,
          proposal_id: envHash,
        };
      }
    }
    const effects = new Set<string>();
    for (const request of reqs) effects.add(request.verb as string);
    if (body.irreversible) effects.add("irreversible");
    const declared = new Set(envelope.declared_effects as string[]);
    if (![...effects].every((e) => declared.has(e))) {
      const detail = `declared effects ${pyRepr(sortStrings([...declared]))} do not cover actual effects ${pyRepr(sortStrings([...effects]))}`;
      this.log.append("decision", {
        producer, class: cls, proposal_id: envHash,
        policy_version: POLICY_VERSION, outcome: "refused",
        fault: "UNDERDECLARED", reasons: [detail],
        effects: sortStrings([...effects]),
      });
      this.refold();
      return {
        status: "REFUSED", refusal: "UNDERDECLARED", detail,
        proposal_id: envHash,
      };
    }
    for (const request of reqs) {
      if (request.verb === "define") {
        try {
          this.dictionary.define((request.args as Json[])[0] as JsonObject);
        } catch (err) {
          if (err instanceof Refusal) {
            // SPEC 3.1: define-check refusals record a fault
            // decision, exactly like UNDERDECLARED, so the
            // verdict replays from the log.
            this.log.append("decision", {
              producer, class: cls, proposal_id: envHash,
              policy_version: POLICY_VERSION, outcome: "refused",
              fault: err.name, reasons: [err.detail],
              effects: sortStrings([...effects]),
            });
            this.refold();
            return {
              status: "REFUSED", refusal: err.name, detail: err.detail,
              proposal_id: envHash,
            };
          }
          throw err;
        }
      }
    }
    const view = this.recordLookup(producer, cls);
    let [outcome, reasons] = decidePolicy(
      producer, envelope.kind as string, effects, view,
      this.standing[producer],
    );
    let decidedBy: string | null = null;
    const policyOutcome = outcome;
    if (this.ruleDecider !== null) {
      const ruled = this.ruleDecider(
        producer, cls, effects, outcome, reasons, reqs,
      );
      if (ruled !== null) {
        [decidedBy, outcome] = [ruled[0], ruled[1] as typeof outcome];
        reasons = [`standing-rule:${decidedBy}`];
      }
    }
    if (waitSatisfied !== null) {
      reasons = [`wait-satisfied:${waitSatisfied}`, ...reasons];
    }
    const decision: JsonObject = {
      producer, class: cls, proposal_id: envHash,
      policy_version: POLICY_VERSION, outcome: OUTCOME_STORED[outcome],
      reasons, effects: sortStrings([...effects]),
    };
    if (decidedBy !== null) {
      decision.decided_by = decidedBy;
      decision.policy_outcome = OUTCOME_STORED[policyOutcome];
    }
    if (outcome === "queue") {
      decision.requests = reqs;
      decision.irreversible = Boolean(body.irreversible ?? false);
      decision.uses = body.uses ?? [];
    }
    this.log.append("decision", decision);
    if (outcome === "allow") {
      this.execute(producer, cls, envHash, body);
    }
    this.refold();
    return {
      status: "decided", outcome, proposal_id: envHash, reasons,
    };
  }

  // ---- execution ----
  execute(
    producer: string, cls: string, proposalId: string, body: JsonObject,
  ): void {
    const requests = (body.requests as JsonObject[] | undefined) ?? [];
    const prepared: (StoredDefinition | null)[] = [];
    for (const request of requests) {
      if (request.verb === "define") {
        prepared.push(
          this.dictionary.define((request.args as Json[])[0] as JsonObject),
        );
      } else {
        prepared.push(null);
      }
    }
    const applied: JsonObject[] = [];
    requests.forEach((request, i) => {
      const stored = prepared[i];
      if (request.verb === "define") {
        this.log.append("definition", {
          producer, definition: stored as StoredDefinition,
        });
      } else {
        const item: JsonObject = { verb: request.verb, args: request.args };
        if (has(request, "outputs")) item.outputs = request.outputs;
        applied.push(item);
      }
    });
    this.log.append("execution", {
      producer, class: cls, proposal_id: proposalId, applied,
      uses: body.uses ?? [],
    });
    this.refold();
  }

  // ---- queue closing ----
  releaseQueued(
    proposalId: string, operator: string, reason?: string,
  ): Verdict {
    const queued = this.state.decision_queue[proposalId] as
      | JsonObject
      | undefined;
    if (queued === undefined) {
      return {
        status: "REFUSED", refusal: "FIELD",
        detail: `no queued proposal with id ${proposalId}`,
      };
    }
    const producer = queued.producer as string;
    const cls = (queued.class as string | undefined) ?? "work";
    this.log.append("decision", {
      producer, class: cls, proposal_id: proposalId,
      policy_version: POLICY_VERSION, outcome: "allow",
      reasons: reason !== undefined ? [reason] : ["released-by-operator"],
      releases: proposalId, released_by: operator,
      effects: queued.effects ?? [],
    });
    const body: JsonObject = {
      requests: queued.requests ?? [], uses: queued.uses ?? [],
    };
    this.execute(producer, cls, proposalId, body);
    this.refold();
    this.pumpWaits();
    return { status: "decided", outcome: "allow", released: proposalId };
  }

  rejectQueued(
    proposalId: string, operator: string, reason?: string,
  ): Verdict {
    const queued = this.state.decision_queue[proposalId] as
      | JsonObject
      | undefined;
    if (queued === undefined) {
      return {
        status: "REFUSED", refusal: "FIELD",
        detail: `no queued proposal with id ${proposalId}`,
      };
    }
    const producer = queued.producer as string;
    const cls = (queued.class as string | undefined) ?? "work";
    this.log.append("decision", {
      producer, class: cls, proposal_id: proposalId,
      policy_version: POLICY_VERSION, outcome: "deny",
      reasons: reason !== undefined ? [reason] : ["rejected-by-operator"],
      rejects: proposalId, rejected_by: operator,
      effects: queued.effects ?? [],
    });
    this.refold();
    this.pumpWaits();
    return { status: "decided", outcome: "deny", rejected: proposalId };
  }

  expireQueued(
    proposalId: string, operator: string, reason?: string,
  ): Verdict {
    const queued = this.state.decision_queue[proposalId] as
      | JsonObject
      | undefined;
    if (queued === undefined) {
      return {
        status: "REFUSED", refusal: "FIELD",
        detail: `no queued proposal with id ${proposalId}`,
      };
    }
    const producer = queued.producer as string;
    const cls = (queued.class as string | undefined) ?? "work";
    this.log.append("decision", {
      producer, class: cls, proposal_id: proposalId,
      policy_version: POLICY_VERSION, outcome: "expired",
      reasons: reason !== undefined ? [reason] : ["expired-in-queue"],
      expires: proposalId, expired_by: operator,
      effects: queued.effects ?? [],
    });
    this.refold();
    this.pumpWaits();
    return { status: "decided", outcome: "expired", expired: proposalId };
  }

  // ---- the wait pump (spec 7.1) ----
  pumpWaits(): void {
    if (this.pumping) return;
    this.pumping = true;
    try {
      for (let pass = 0; pass < 64; pass++) {
        let changed = false;
        const snapshot: [string, JsonObject][] = Object.entries(
          this.state.decision_queue,
        )
          .filter(([, body]) => isObj((body as JsonObject).wait))
          .map(([pid, body]) => [pid, deepClone(body) as JsonObject]);
        for (const [pid] of snapshot) {
          if (!has(this.state.decision_queue, pid)) continue;
          if (
            this.pumpOneWaiter(
              pid, this.state.decision_queue[pid] as JsonObject,
            )
          ) {
            changed = true;
          }
        }
        if (!changed) break;
      }
    } finally {
      this.pumping = false;
    }
  }

  pumpOneWaiter(proposalId: string, queued: JsonObject): boolean {
    const wait = queued.wait as JsonObject;
    const guard = wait.guard as string;
    const producer = queued.producer as string;
    let stack: Json[];
    try {
      const [s, emitted] = this.evaluateWord(guard, producer, [
        { proposal_id: proposalId },
      ]);
      if (emitted.length) {
        throw new Refusal(
          "SPEC", `wait guard ${guard} emitted requests ${pyRepr(emitted)}`,
        );
      }
      if (!pyEq(s, [true]) && !pyEq(s, [false])) {
        throw new Refusal(
          "FIELD",
          `wait guard ${guard} must leave exactly one bool, got ${pyRepr(s)}`,
        );
      }
      stack = s;
    } catch (err) {
      if (!(err instanceof Refusal)) throw err;
      const marker = queued.wait_refusal_at;
      if (
        marker !== undefined &&
        marker !== null &&
        marker === this.log.entries.length - 1
      ) {
        return false;
      }
      this.log.append("decision", {
        producer, class: (queued.class as string | undefined) ?? "work",
        proposal_id: proposalId, policy_version: POLICY_VERSION,
        outcome: "queued",
        reasons: [`wait-guard-refused:${err.name}`],
        effects: queued.effects ?? [], requests: queued.requests ?? [],
        irreversible: Boolean(queued.irreversible ?? false),
        uses: queued.uses ?? [], wait: deepClone(wait) as Json,
        wait_refusal_at: this.log.entries.length,
      });
      this.refold();
      return true;
    }
    if (pyEq(stack, [true])) {
      this.decideWaiterFresh(proposalId, queued, guard);
      return true;
    }
    if (this.log.entries.length > (wait.deadline_seq as number)) {
      this.expireQueued(proposalId, "wait-pump", `wait-expired:${guard}`);
      return true;
    }
    return false;
  }

  decideWaiterFresh(
    proposalId: string, queued: JsonObject, guard: string,
  ): void {
    const producer = queued.producer as string;
    const cls = (queued.class as string | undefined) ?? "work";
    const effects = new Set((queued.effects as string[] | undefined) ?? []);
    const view = this.recordLookup(producer, cls);
    let [outcome, reasons] = decidePolicy(
      producer, "proposal", effects, view, this.standing[producer],
    );
    let decidedBy: string | null = null;
    const policyOutcome = outcome;
    if (this.ruleDecider !== null) {
      const ruled = this.ruleDecider(
        producer, cls, effects, outcome, reasons,
        queued.requests as Json[] | undefined,
      );
      if (ruled !== null) {
        [decidedBy, outcome] = [ruled[0], ruled[1] as typeof outcome];
        reasons = [`standing-rule:${decidedBy}`];
      }
    }
    reasons = [`wait-satisfied:${guard}`, ...reasons];
    const decision: JsonObject = {
      producer, class: cls, proposal_id: proposalId,
      policy_version: POLICY_VERSION, outcome: OUTCOME_STORED[outcome],
      reasons, effects: sortStrings([...effects]),
    };
    if (decidedBy !== null) {
      decision.decided_by = decidedBy;
      decision.policy_outcome = OUTCOME_STORED[policyOutcome];
    }
    if (outcome === "allow") {
      decision.releases = proposalId;
      this.log.append("decision", decision);
      const body: JsonObject = {
        requests: queued.requests ?? [], uses: queued.uses ?? [],
      };
      this.execute(producer, cls, proposalId, body);
    } else if (outcome === "deny") {
      decision.releases = proposalId;
      this.log.append("decision", decision);
    } else if (outcome === "queue") {
      decision.requests = queued.requests ?? [];
      decision.irreversible = Boolean(queued.irreversible ?? false);
      decision.uses = queued.uses ?? [];
      this.log.append("decision", decision);
      this.refold();
    }
    this.refold();
  }
}

// ---------------------------------------------------------------------------
// senses.py — sense computation (spec section 11.3).
// Method strings are copied verbatim from the Python module: they
// are part of the published reading and of the golden vectors.
// ---------------------------------------------------------------------------

const DRIFT_WINDOW = 25;

export const EXCLUSIVE_SEATS = new Set([
  "zcode", "mcode", "claude-code", "gpu", "stage", "kimi", "box",
]);

const CONTENTION_METHOD =
  "contention sense: read set = committed units with prefix " +
  "booking/<box>/ (the subject's box); a committed booking " +
  "contends iff ALL of: status is \"active\" only (done, " +
  "cancelled, preempted and expired bookings are inert); its " +
  "id differs from the candidate's id (a booking never " +
  "contends with itself -- a committed row whose id equals " +
  "the candidate's id is excluded even when its producer " +
  "differs); its producer differs from the candidate's " +
  "producer (a same-producer overlap is a renewal, not " +
  "contention); its checkby is null or >= the candidate start " +
  "(a booking whose check-by passed before the candidate " +
  "starts is dead by the board protocol); seat rules -- equal " +
  "seats contend iff the seat is in {zcode, mcode, " +
  "claude-code, gpu, stage, kimi, box}, \"box\" contends with " +
  "every seat, other distinct seats do not contend; and " +
  "strict interval overlap candidate.start < other.end and " +
  "other.start < candidate.end (touching endpoints do not " +
  "contend). Value reports every contender sorted by id, " +
  "their count, the maximum contender rank (-1 when none), " +
  "the highest-rank contender's id (ties: smallest id, null " +
  "when none), and \"unclassified\": the sorted seat strings " +
  "-- the candidate's seat and the seats of status-\"active\" " +
  "rows under the prefix -- that are in neither the exclusive " +
  "set nor {\"detached\"}. Rank otherwise plays no part in " +
  "contention itself.";

const AUTHORITY_METHOD =
  "authority sense: read set = log entries passing three " +
  "filters -- entry kind is \"execution\", the entry body's " +
  "producer is \"operator\", and the entry's applied writes " +
  "include a write to unit authority/<producer>. Among those " +
  "writes the LATEST wins: its value (an integer) is the " +
  "ceiling, so a later lower grant is a downward revocation; " +
  "grants is the count of such writes. Only operator-authored " +
  "writes count: a producer's own write to authority/<self> " +
  "may land in units under policy/1 but fails the producer " +
  "filter, so it is visible in the log and inert here. The " +
  "unit's current value alone is not evidence of a grant. No " +
  "operator grant -> ceiling null, grants 0.";

export interface SenseReading {
  value: Json;
  method: string;
  as_of_seq: number;
}

type SenseFn = (
  entries: StoredEntry[],
  state: FoldedState,
  subject: string | null,
  runtime: { [k: string]: unknown } | null,
) => { value: Json; method: string };

function seatsConflict(candidateSeat: unknown, otherSeat: unknown): boolean {
  if (candidateSeat === otherSeat) {
    return EXCLUSIVE_SEATS.has(candidateSeat as string);
  }
  if (candidateSeat === "box" || otherSeat === "box") return true;
  return false;
}

const SENSES: { [name: string]: SenseFn } = {
  "queue-depth": (_entries, state) => ({
    value: Object.keys(state.decision_queue).length,
    method: "count of folded decision_queue entries",
  }),
  "output-use": (entries, _state, subject) => {
    if (!subject) throw new Error("output-use sense needs a producer subject");
    const [outputs, used] = outputsAndUses(entries, subject);
    const ratioBp = outputs ? Math.floor((10000 * used) / outputs) : 0;
    return {
      value: { producer: subject, outputs, used, ratio_bp: ratioBp },
      method:
        "records projection: outputs listed on executed proposals vs outputs named in later proposals' uses",
    };
  },
  starvation: (_entries, _state, _subject, runtime) => {
    const scheduler = runtime?.scheduler as
      | { stats: () => JsonObject }
      | undefined;
    if (!scheduler) {
      return {
        value: { status: "no-runtime" },
        method:
          "starvation evidence needs a live scheduler's counters; none was supplied at publish time",
      };
    }
    const stats = scheduler.stats();
    const flows: JsonObject = {};
    for (const [flow, data] of Object.entries(
      stats.flows as JsonObject,
    )) {
      const d = data as JsonObject;
      flows[flow] = {
        waiting: d.waiting,
        served_size: d.served_size,
        weight_bp: Math.trunc(10000 * (d.weight as number)),
      };
    }
    return {
      value: {
        virtual_time: Math.trunc(stats.virtual_time as number),
        flows,
      },
      method:
        "scheduler counters at publish time: per-flow waiting items, served size, current weight",
    };
  },
  "calibration-drift": (entries) => {
    const outcomes: string[] = [];
    for (const e of entries) {
      if (
        e.kind === "decision" &&
        (e.body.outcome === "allow" || e.body.outcome === "deny")
      ) {
        outcomes.push(e.body.outcome as string);
      }
    }
    if (outcomes.length < 2 * DRIFT_WINDOW) {
      return {
        value: { status: "insufficient-data", decisions: outcomes.length },
        method: `stub: needs ${2 * DRIFT_WINDOW} decisions for two windows`,
      };
    }
    const baseline = outcomes.slice(0, DRIFT_WINDOW);
    const recent = outcomes.slice(-DRIFT_WINDOW);
    const allowBp = (w: string[]) =>
      Math.floor((10000 * w.filter((o) => o === "allow").length) / w.length);
    return {
      value: {
        status: "stub",
        drift_bp: Math.abs(allowBp(recent) - allowBp(baseline)),
        baseline_allow_bp: allowBp(baseline),
        recent_allow_bp: allowBp(recent),
        window: DRIFT_WINDOW,
      },
      method:
        `stub: kernel-wide allow-rate drift between the first and last ${DRIFT_WINDOW} decisions; per-rule calibration arrives with the learner`,
    };
  },
  contention: (_entries, state, subject) => {
    if (!subject) throw new Error("contention sense needs a subject");
    const all = subject.split("/");
    if (all.length < 6) {
      throw new Error(
        `contention subject must be <box>/<seat>/<start>/<end>/<producer>/<id>: ${pyRepr(subject)}`,
      );
    }
    const [seat, start, end, producer, candId] = all.slice(-5);
    const box = all.slice(0, -5).join("/");
    if (!/^[+-]?\d+$/.test(start) || !/^[+-]?\d+$/.test(end)) {
      throw new Error(
        `contention subject start/end must be integer minutes: ${pyRepr(subject)}`,
      );
    }
    const candStart = parseInt(start, 10);
    const candEnd = parseInt(end, 10);
    const prefix = `booking/${box}/`;
    const contenders: JsonObject[] = [];
    const seatsSeen = new Set<string>([seat]);
    for (const unit of sortStrings(Object.keys(state.units))) {
      if (!unit.startsWith(prefix)) continue;
      const other = state.units[unit];
      if (!isObj(other)) continue;
      if (other.status !== "active") continue;
      if (typeof other.seat === "string") seatsSeen.add(other.seat);
      if (pyEq(other.id, candId)) continue;
      if (other.producer === producer) continue;
      const checkby = other.checkby;
      if (checkby !== null && checkby !== undefined &&
          (checkby as number) < candStart) {
        continue;
      }
      if (!seatsConflict(seat, other.seat)) continue;
      if (
        !(candStart < (other.end as number) &&
          (other.start as number) < candEnd)
      ) {
        continue;
      }
      contenders.push({
        id: other.id, producer: other.producer, seat: other.seat,
        start: other.start, end: other.end,
        rank: (other.rank as Json | undefined) ?? 0,
      });
    }
    contenders.sort((a, b) => compareCodePoints(a.id as string, b.id as string));
    let maxRank = -1;
    let topId: Json = null;
    if (contenders.length) {
      maxRank = Math.max(...contenders.map((c) => c.rank as number));
      topId = contenders
        .filter((c) => c.rank === maxRank)
        .map((c) => c.id as string)
        .sort(compareCodePoints)[0];
    }
    const unclassified = sortStrings(
      [...seatsSeen].filter(
        (s) => !EXCLUSIVE_SEATS.has(s) && s !== "detached",
      ),
    );
    return {
      value: {
        contenders: contenders as Json, count: contenders.length,
        max_rank: maxRank, top_id: topId, unclassified,
      },
      method: CONTENTION_METHOD,
    };
  },
  authority: (entries, _state, subject) => {
    if (!subject) throw new Error("authority sense needs a producer subject");
    const unit = `authority/${subject}`;
    let ceiling: Json = null;
    let grants = 0;
    for (const entry of entries) {
      if (entry.kind !== "execution") continue;
      const body = entry.body;
      if (body.producer !== "operator") continue;
      const applied = Array.isArray(body.applied) ? body.applied : [];
      for (const item of applied) {
        if (
          isObj(item) &&
          item.verb === "write" &&
          Array.isArray(item.args) &&
          item.args[0] === unit
        ) {
          ceiling = item.args[1];
          grants += 1;
        }
      }
    }
    return { value: { ceiling, grants }, method: AUTHORITY_METHOD };
  },
};

export function computeSense(
  name: string,
  entries: StoredEntry[],
  state: FoldedState,
  runtime: { [k: string]: unknown } | null = null,
): SenseReading {
  const idx = name.indexOf(":");
  const base = idx === -1 ? name : name.slice(0, idx);
  const subject = idx === -1 ? null : name.slice(idx + 1) || null;
  if (!has(SENSES, base)) throw new Error(`unknown sense: ${name}`);
  const reading = SENSES[base](entries, state, subject, runtime);
  return {
    value: reading.value,
    method: reading.method,
    as_of_seq: entries.length ? entries[entries.length - 1].seq : -1,
  };
}

// ---------------------------------------------------------------------------
// learner.py — the section 12.1 shape signature.
// ---------------------------------------------------------------------------

const SHELL_PROGRAMS = new Set(["sh", "bash", "dash", "zsh", "ksh"]);
const SEGMENT_SPLIT = /&&|\|\||[;|\n]/;

function basenameOf(path: unknown): string {
  const s = String(path);
  const idx = s.lastIndexOf("/");
  return idx === -1 ? s : s.slice(idx + 1);
}

function abstractToken(token: string): string {
  if (token.length > 1 && token.startsWith("-")) {
    return token.split("=", 1)[0];
  }
  if (token.includes("://")) return "<url>";
  if (token.includes("/")) return "<path>";
  if (/^\p{Nd}+$/u.test(token)) return "<num>";
  return token;
}

// POSIX shell tokenisation (Python shlex.split, comments off).
export function shlexSplit(raw: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let started = false;
  let i = 0;
  const push = () => {
    if (started) tokens.push(current);
    current = "";
    started = false;
  };
  while (i < raw.length) {
    const ch = raw[i];
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      push();
      i++;
    } else if (ch === "'") {
      started = true;
      i++;
      while (i < raw.length && raw[i] !== "'") {
        current += raw[i];
        i++;
      }
      if (i >= raw.length) throw new Error("No closing quotation");
      i++;
    } else if (ch === '"') {
      started = true;
      i++;
      let closed = false;
      while (i < raw.length) {
        if (raw[i] === '"') {
          closed = true;
          i++;
          break;
        }
        if (
          raw[i] === "\\" &&
          i + 1 < raw.length &&
          ['"', "\\", "$", "`", "\n"].includes(raw[i + 1])
        ) {
          if (raw[i + 1] !== "\n") current += raw[i + 1];
          i += 2;
        } else {
          current += raw[i];
          i++;
        }
      }
      if (!closed) throw new Error("No closing quotation");
    } else if (ch === "\\") {
      started = true;
      if (i + 1 < raw.length) {
        if (raw[i + 1] !== "\n") current += raw[i + 1];
        i += 2;
      } else {
        i++;
      }
    } else {
      started = true;
      current += ch;
      i++;
    }
  }
  push();
  return tokens;
}

function commandSkeleton(cmd: Json[]): string[][] {
  const tokens = cmd.map((t) => String(t));
  let segments: string[][];
  if (
    tokens.length >= 3 &&
    tokens[1] === "-c" &&
    SHELL_PROGRAMS.has(basenameOf(tokens[0]))
  ) {
    segments = [];
    for (const raw of tokens[2].split(SEGMENT_SPLIT)) {
      let parts: string[];
      try {
        parts = shlexSplit(raw);
      } catch {
        parts = raw.split(/\s+/).filter((p) => p.length > 0);
      }
      if (parts.length) segments.push(parts);
    }
  } else {
    segments = tokens.length ? [tokens] : [];
  }
  return segments.map((parts) => [
    basenameOf(parts[0]),
    ...parts.slice(1).map((t) => abstractToken(t)),
  ]);
}

function sendHost(channel: string): string {
  // Python urlparse(...).hostname: lowercased host of the netloc,
  // or "" when the channel carries no netloc.
  let rest = channel;
  const scheme = /^[A-Za-z][A-Za-z0-9+.-]*:/.exec(rest);
  if (scheme) rest = rest.slice(scheme[0].length);
  if (!rest.startsWith("//")) return "";
  rest = rest.slice(2);
  const netloc = rest.split(/[/?#]/, 1)[0];
  const hostport = netloc.slice(netloc.lastIndexOf("@") + 1);
  if (hostport.startsWith("[")) {
    const end = hostport.indexOf("]");
    return (end === -1 ? hostport : hostport.slice(1, end)).toLowerCase();
  }
  return hostport.split(":", 1)[0].toLowerCase();
}

export function shapeSignature(requests: Json[] | null | undefined): Json {
  const components: Json[] = [];
  for (const request of requests ?? []) {
    if (!isObj(request)) {
      components.push([null, ""]);
      continue;
    }
    const verb = request.verb;
    const args = Array.isArray(request.args) ? request.args : [];
    let detail: Json = "";
    if (
      verb === "dispatch" &&
      args.length &&
      isObj(args[0]) &&
      Array.isArray(args[0].cmd)
    ) {
      detail = commandSkeleton(args[0].cmd as Json[]) as Json;
    } else if (verb === "write" && args.length && typeof args[0] === "string") {
      const base = basenameOf(args[0]);
      detail = base.includes(".") ? base.slice(base.lastIndexOf(".")) : "";
    } else if (verb === "send" && args.length && typeof args[0] === "string") {
      detail = sendHost(args[0]);
    }
    components.push([verb ?? null, detail]);
  }
  return components as Json;
}

// ---------------------------------------------------------------------------
// anchor.py — chain-head anchoring verification (spec section 15.5).
// Ed25519 via Node's built-in crypto: raw keys are wrapped in the
// fixed RFC 8410 DER prefixes (SPKI for verify, PKCS#8 for seed
// derivation). No new dependency.
// ---------------------------------------------------------------------------

export const ANCHOR_FORMAT = "jacquard/anchor/1";
const BODY_KEYS = [
  "format", "log_id", "label", "checkpoint_seq", "log_length",
  "head_hash", "spec", "prev_checkpoint",
];
const HEX64_RE = /^[0-9a-f]{64}$/;
const HEX128_RE = /^[0-9a-f]{128}$/;
const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");
const PKCS8_PREFIX = Buffer.from(
  "302e020100300506032b657004220420", "hex",
);

export function ed25519PublicKeyFromRaw(raw: Buffer) {
  return createPublicKey({
    key: Buffer.concat([SPKI_PREFIX, raw]),
    format: "der",
    type: "spki",
  });
}

export function ed25519Verify(
  pubkeyHex: string, message: Uint8Array, sigHex: string,
): boolean {
  try {
    const key = ed25519PublicKeyFromRaw(Buffer.from(pubkeyHex, "hex"));
    return cryptoVerify(
      null, message, key, Buffer.from(sigHex, "hex"),
    );
  } catch {
    return false;
  }
}

export function ed25519PubFromSeed(seedHex: string): string {
  const priv = createPrivateKey({
    key: Buffer.concat([PKCS8_PREFIX, Buffer.from(seedHex, "hex")]),
    format: "der",
    type: "pkcs8",
  });
  const pub = createPublicKey(priv);
  const der = pub.export({ format: "der", type: "spki" }) as Buffer;
  return der.subarray(der.length - 32).toString("hex");
}

export function checkpointHash(body: JsonObject): string {
  return hash(body as Json);
}

export function logIdOf(entries: StoredEntry[]): string {
  return entries.length ? entries[0].hash : GENESIS_PREV;
}

export function headAt(entries: StoredEntry[], length: number): string {
  return length === 0 ? GENESIS_PREV : entries[length - 1].hash;
}

export function validateAnchorBody(body: unknown): string | null {
  if (!isObj(body)) return "body is not an object";
  const keys = Object.keys(body);
  if (
    keys.length !== BODY_KEYS.length ||
    !BODY_KEYS.every((k) => keys.includes(k))
  ) {
    return `body keys are ${pyRepr(sortStrings(keys))}, expected exactly ${pyRepr(sortStrings([...BODY_KEYS]))}`;
  }
  if (body.format !== ANCHOR_FORMAT) {
    return `format is ${pyRepr(body.format)}`;
  }
  if (typeof body.log_id !== "string" || !HEX64_RE.test(body.log_id)) {
    return "log_id is not hex64";
  }
  if (typeof body.label !== "string") return "label is not a string";
  if (
    typeof body.checkpoint_seq !== "number" ||
    !Number.isInteger(body.checkpoint_seq) ||
    body.checkpoint_seq < 0
  ) {
    return "checkpoint_seq is not an integer >= 0";
  }
  if (
    typeof body.log_length !== "number" ||
    !Number.isInteger(body.log_length) ||
    body.log_length < 0
  ) {
    return "log_length is not an integer >= 0";
  }
  if (typeof body.head_hash !== "string" || !HEX64_RE.test(body.head_hash)) {
    return "head_hash is not hex64";
  }
  // Spec 15.1 (0.6): the anchor format did not change in 0.6, so
  // checkpoints issued under 0.5 remain valid; refuse any other.
  if (body.spec !== "jacquard/0.5" && body.spec !== "jacquard/0.6" && body.spec !== "jacquard/0.7") {
    return `spec is ${pyRepr(body.spec)}, expected "jacquard/0.5", "jacquard/0.6" or "jacquard/0.7"`;
  }
  const prev = body.prev_checkpoint;
  if (body.checkpoint_seq === 0 && prev !== null) {
    return "checkpoint_seq 0 must carry prev_checkpoint null";
  }
  if (
    (body.checkpoint_seq as number) > 0 &&
    (typeof prev !== "string" || !HEX64_RE.test(prev))
  ) {
    return "prev_checkpoint is not hex64";
  }
  return null;
}

export interface AnchorResult {
  outcome: string | null;
  log_id: string;
  log_length: number;
  anchored_length: number;
  unanchored_tail: number;
  checkpoints_checked: number;
  internal_chain_ok: boolean;
  failure: JsonObject | null;
}

function scheduledKey(
  schedule: [number, string][], checkpointSeq: number,
): string | null {
  let chosen: string | null = null;
  for (const [fromSeq, pubkeyHex] of schedule) {
    if (checkpointSeq >= fromSeq) chosen = pubkeyHex;
  }
  return chosen;
}

export function authenticateHistory(
  history: JsonObject[],
  schedule: [number, string][],
): [boolean, string | null, number | null] {
  let prevHash: string | null = null;
  for (let expectedSeq = 0; expectedSeq < history.length; expectedSeq++) {
    const envelope = history[expectedSeq];
    const body = envelope.body as JsonObject;
    const detail = validateAnchorBody(body);
    if (detail !== null) {
      return [false, `checkpoint ${expectedSeq}: ${detail}`,
        (body.checkpoint_seq as number | undefined) ?? null];
    }
    if (body.checkpoint_seq !== expectedSeq) {
      return [
        false,
        `checkpoint sequence gap: expected seq ${expectedSeq}, found ${body.checkpoint_seq as number}`,
        body.checkpoint_seq as number,
      ];
    }
    if (body.prev_checkpoint !== prevHash) {
      return [
        false,
        `checkpoint ${expectedSeq}: prev_checkpoint does not recompute`,
        expectedSeq,
      ];
    }
    const pinned = scheduledKey(schedule, expectedSeq);
    if (pinned === null || envelope.pubkey !== pinned) {
      return [
        false,
        `checkpoint ${expectedSeq}: envelope pubkey is not the pinned key for its sequence`,
        expectedSeq,
      ];
    }
    if (
      typeof envelope.sig !== "string" ||
      !HEX128_RE.test(envelope.sig) ||
      !ed25519Verify(pinned, canonicalBytes(body as Json), envelope.sig)
    ) {
      return [
        false,
        `checkpoint ${expectedSeq}: signature does not verify`,
        expectedSeq,
      ];
    }
    prevHash = checkpointHash(body);
  }
  return [true, null, null];
}

export function historyFor(
  envelopes: JsonObject[], logId: string,
): JsonObject[] {
  return envelopes
    .filter(
      (e) => isObj(e.body) && (e.body as JsonObject).log_id === logId,
    )
    .sort(
      (a, b) =>
        ((a.body as JsonObject).checkpoint_seq as number) -
        ((b.body as JsonObject).checkpoint_seq as number),
    );
}

export function verifyAnchor(
  entries: StoredEntry[],
  envelopes: JsonObject[],
  pubkeyHex: string,
  schedule?: [number, string][],
): AnchorResult {
  const sched = schedule ?? [[0, pubkeyHex]];
  const logId = logIdOf(entries);
  const result: AnchorResult = {
    outcome: null,
    log_id: logId,
    log_length: entries.length,
    anchored_length: 0,
    unanchored_tail: entries.length,
    checkpoints_checked: 0,
    internal_chain_ok: verifyInternalChain(entries),
    failure: null,
  };
  const history = historyFor(envelopes, logId);
  if (!history.length) {
    result.outcome = "unanchored";
    return result;
  }
  const [ok, detail, offender] = authenticateHistory(history, sched);
  if (!ok) {
    result.outcome = "failed";
    result.failure = {
      stage: "history", checkpoint_seq: offender, detail,
    };
    return result;
  }
  if (!result.internal_chain_ok) {
    result.outcome = "failed";
    result.failure = {
      stage: "internal", checkpoint_seq: null,
      detail: "presented log fails its own hash-chain verification",
    };
    return result;
  }
  for (const envelope of history) {
    const body = envelope.body as JsonObject;
    result.checkpoints_checked += 1;
    if ((body.log_length as number) > entries.length) {
      result.unanchored_tail = entries.length - result.anchored_length;
      result.outcome = "failed";
      result.failure = {
        stage: "prefix",
        checkpoint_seq: body.checkpoint_seq,
        detail:
          `checkpoint anchors length ${body.log_length as number}, presented log has ${entries.length} entries (truncated or missing anchored history)`,
        expected_head: body.head_hash,
        actual_head: null,
      };
      return result;
    }
    const actual = headAt(entries, body.log_length as number);
    if (actual !== body.head_hash) {
      result.unanchored_tail = entries.length - result.anchored_length;
      result.outcome = "failed";
      result.failure = {
        stage: "prefix",
        checkpoint_seq: body.checkpoint_seq,
        detail:
          `first divergent checkpoint: checkpoint ${body.checkpoint_seq as number} anchors length ${body.log_length as number} at head ${body.head_hash as string}, presented log's head at that length is ${actual}`,
        expected_head: body.head_hash,
        actual_head: actual,
      };
      return result;
    }
    result.anchored_length = body.log_length as number;
  }
  result.unanchored_tail = entries.length - result.anchored_length;
  result.outcome = result.unanchored_tail === 0 ? "verified" : "verified_to_anchor";
  return result;
}

// SHA-256 hex helper for drill evidence.
export function sha256Hex(data: string | Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}
