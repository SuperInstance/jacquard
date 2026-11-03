// Jacquard conformance runner — Phase 3 slice 8, completed by
// Phase 7 slice 19 (the full TypeScript port).
//
// Run from this directory:  node check.ts
// Prints one PASS/FAIL line per check and exits non-zero on any
// FAIL. There are no SKIP lines: slice 19 ported the dictionary
// + evaluator, the sequencer (with the wait pump), sense
// computation, the section 12.1 shape signature, and the
// section 15 anchor verifier into ./kernel.ts, so every golden
// vector section is now executed and compared for real.

import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  SPEC_SEAL,
  canonical,
  entryHash,
  envelopeId,
  fold,
  foldStateHash,
  hash,
  makeEntry,
  stateHash,
  validateEnvelope,
  verifyChain,
  type Envelope,
  type Json,
  type JsonObject,
  type StoredEntry,
} from "./jacquard.ts";

import {
  Refusal,
  Sequencer,
  computeSense,
  deepClone,
  ed25519PubFromSeed,
  ed25519Verify,
  checkpointHash,
  shapeSignature,
  verifyAnchor,
  type SenseReading,
} from "./kernel.ts";
import { canonicalBytes } from "./jacquard.ts";

function deepEq(a: unknown, b: unknown): boolean {
  return canonical(a as Json) === canonical(b as Json);
}

function makeEnvelopeTs(
  producer: string,
  kind: string,
  body: Json,
  declaredEffects: string[],
  id: string,
): JsonObject {
  return {
    v: 1,
    id,
    producer,
    kind,
    body,
    declared_effects: [...new Set(declaredEffects)].sort(),
    spec_seal: SPEC_SEAL,
  };
}

const here = dirname(fileURLToPath(import.meta.url));
const vectorsPath = join(here, "..", "..", "spec", "vectors", "vectors.json");
const replayPath = join(here, "..", "replay-log.json.gz");

let failures = 0;

function report(status: "PASS" | "FAIL" | "SKIP", label: string, detail: string): void {
  console.log(`${status} ${label}: ${detail}`);
  if (status === "FAIL") failures++;
}

function loadJson(path: string): Json {
  return JSON.parse(readFileSync(path, "utf8")) as Json;
}

const vectors = loadJson(vectorsPath) as {
  spec_seal: string;
  entries: { seq: number; kind: string; body: StoredEntry["body"]; hash: string }[];
  envelope: { envelope: Envelope; id: string };
  state: { state_hash: string; units: { [k: string]: Json } };
  definitions: { definition: JsonObject; stored: JsonObject }[];
  senses: {
    [sense: string]: {
      entries: StoredEntry[];
      subject: string;
      expect: SenseReading;
    }[];
  };
  anchor: {
    test_seed: string;
    envelope: JsonObject;
    checkpoint_hash: string;
  };
};

interface Replay {
  entries: StoredEntry[];
  expected_state_hash: string;
  entry_count: number;
}

let replay: Replay | null = null;
let replayError: string | null = null;
try {
  replay = JSON.parse(
    gunzipSync(readFileSync(replayPath)).toString("utf8"),
  ) as Replay;
} catch (err) {
  replayError = `cannot load ${replayPath}: ${(err as Error).message}`;
}

// --- a. spec_seal -----------------------------------------------------------
// The seal computed from the spec text's rule (§3: hash of the string
// "jacquard-spec/0.5") must equal the seal recorded in vectors.json.
{
  const ok = SPEC_SEAL === vectors.spec_seal;
  report(
    ok ? "PASS" : "FAIL",
    "a. spec_seal",
    ok
      ? `computed seal ${SPEC_SEAL} equals vectors.spec_seal`
      : `computed ${SPEC_SEAL}, vectors record ${vectors.spec_seal}`,
  );
}

// --- b. vector entries rebuild + chain --------------------------------------
// Rebuild the three vector entries from (kind, body), supplying seq, the
// prev chain and spec "jacquard/0.5"; each must reproduce its recorded hash,
// and the chain must verify.
const rebuiltEntries: StoredEntry[] = [];
{
  let prev = "0".repeat(64);
  let allOk = true;
  const problems: string[] = [];
  vectors.entries.forEach((ve, i) => {
    const entry = makeEntry(ve.seq, prev, ve.kind, ve.body);
    const h = entryHash(entry);
    if (h !== ve.hash) {
      allOk = false;
      problems.push(`entry ${i} (${ve.kind}): computed ${h}, recorded ${ve.hash}`);
    }
    rebuiltEntries.push({ ...entry, hash: ve.hash });
    prev = ve.hash;
  });
  const chain = verifyChain(rebuiltEntries);
  if (!chain.ok) {
    allOk = false;
    problems.push(`chain: ${chain.failure}`);
  }
  report(
    allOk ? "PASS" : "FAIL",
    "b. vector entries",
    allOk
      ? `all ${vectors.entries.length} entries rebuilt from (kind, body) reproduce their recorded hashes; chain verifies`
      : problems.join("; "),
  );
}

// --- c. fold of first two vector entries vs checkpoint ----------------------
{
  const checkpoint = vectors.entries[2];
  const recorded =
    checkpoint.kind === "checkpoint"
      ? (checkpoint.body.state_hash as string)
      : "(third entry is not a checkpoint)";
  const computed = foldStateHash(rebuiltEntries.slice(0, 2));
  const ok = computed === recorded;
  report(
    ok ? "PASS" : "FAIL",
    "c. vector fold",
    ok
      ? `folding the first two entries gives state_hash ${computed}, as recorded in the checkpoint body`
      : `folded state_hash ${computed}, checkpoint records ${recorded}`,
  );
}

// --- d. envelope id ----------------------------------------------------------
{
  const problems = validateEnvelope(vectors.envelope.envelope);
  const computed = envelopeId(vectors.envelope.envelope);
  const ok = computed === vectors.envelope.id && problems.length === 0;
  const detail = [
    computed === vectors.envelope.id
      ? `envelope recomputes to its recorded id ${computed}`
      : `computed id ${computed}, recorded ${vectors.envelope.id}`,
    ...(problems.length ? [`validation problems: ${problems.join("; ")}`] : []),
  ].join("; ");
  report(ok ? "PASS" : "FAIL", "d. envelope id", detail);
}

// --- e. replay log: every hash recomputes + chain verifies -------------------
if (replay === null) {
  report("FAIL", "e. replay hashes+chain", replayError as string);
  report("FAIL", "f. replay fold", replayError as string);
} else {
  const entries = replay.entries;
  let recomputed = 0;
  let firstBad: string | null = null;
  for (const e of entries) {
    if (entryHash(e) === e.hash) recomputed++;
    else if (firstBad === null) firstBad = `entry seq ${e.seq} (${e.kind})`;
  }
  const chain = verifyChain(entries);
  const ok = recomputed === entries.length && chain.ok;
  report(
    ok ? "PASS" : "FAIL",
    "e. replay hashes+chain",
    ok
      ? `${recomputed} entries checked: every recorded hash recomputes and the chain verifies end to end`
      : `recomputed ${recomputed}/${entries.length}` +
          (firstBad ? `; first mismatch at ${firstBad}` : "") +
          (chain.ok ? "" : `; chain failure: ${chain.failure}`),
  );

// --- f. replay fold vs expected_state_hash -----------------------------------
  const foldedHash = stateHash(fold(replay.entries));
  const foldOk = foldedHash === replay.expected_state_hash;
  report(
    foldOk ? "PASS" : "FAIL",
    "f. replay fold",
    foldOk
      ? `folding all ${replay.entries.length} replay entries yields state_hash ${foldedHash} == expected_state_hash`
      : `folded state_hash ${foldedHash}, expected ${replay.expected_state_hash}`,
  );
} // end replay-present branch

// --- g. full log: every emitted entry kind, hashes + fold --------------------
// Added by the coordinator after the GAPS.md round: the replay
// fixture contains only 4 of the 12 entry kinds, so a second
// fixture (generated by the Python kernel, folded here from the
// spec) exercises the other kinds — machine, transition, budget,
// price, rule, import included.
{
  const fullPath = join(here, "..", "full-log.json.gz");
  try {
    const raw = readFileSync(fullPath);
    const full = JSON.parse(gunzipSync(raw).toString("utf-8"));
    const entries = full.entries;
    let recomputed = 0;
    for (const e of entries) if (entryHash(e) === e.hash) recomputed++;
    const chain = verifyChain(entries);
    const foldedHash = stateHash(fold(entries));
    const ok = recomputed === entries.length && chain.ok &&
      foldedHash === full.expected_state_hash;
    report(
      ok ? "PASS" : "FAIL",
      "g. full-log hashes+chain+fold",
      ok
        ? `${recomputed} entries across all emitted kinds: hashes recompute, chain verifies, fold yields state_hash ${foldedHash}`
        : `recomputed ${recomputed}/${entries.length}; chain ${chain.ok}; folded ${foldedHash}, expected ${full.expected_state_hash}`,
    );
  } catch (err) {
    report("FAIL", "g. full-log hashes+chain+fold",
      `cannot load ${fullPath}: ${(err as Error).message}`);
  }
}

// --- vectors.definitions: dictionary + evaluator (spec §§4-5) ----------------
// Mirrors tests/test_vectors.py::test_definition_vectors exactly:
// each definition is submitted to a fresh TS sequencer, must be
// accepted, and its stored form must equal the recorded stored
// form (computed effects and refs included) canonically.
{
  const seq = new Sequencer();
  const problems: string[] = [];
  for (const item of vectors.definitions) {
    const defn = item.definition;
    const verdict = seq.submit(
      makeEnvelopeTs(
        "operator", "definition", defn,
        (defn.declared_effects as string[] | undefined) ?? [],
        "vec-" + (defn.name as string),
      ),
    );
    if (verdict.status !== "accepted") {
      problems.push(
        `${defn.name as string}: verdict ${JSON.stringify(verdict)}`,
      );
      continue;
    }
    const stored =
      seq.state.dictionary[defn.name as string].slice(-1)[0].definition;
    if (!deepEq(stored, item.stored)) {
      problems.push(
        `${defn.name as string}: stored ${canonical(stored as Json)} != recorded ${canonical(item.stored as Json)}`,
      );
    }
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "vectors.definitions",
    problems.length
      ? problems.join("; ")
      : `all ${vectors.definitions.length} definitions accepted by the TS dictionary with stored forms (computed effects + refs) identical to the recorded vectors`,
  );
}

// --- vectors.state: sequencer execution end to end (spec §7) -----------------
// Mirrors tests/test_vectors.py::test_state_vector: replay the
// generator's scenario (both definitions, then the write
// proposal) through the TS sequencer; units, state hash and the
// refolded state hash must all equal the recorded state section.
{
  const seq = new Sequencer();
  for (const item of vectors.definitions) {
    seq.submit(
      makeEnvelopeTs(
        "operator", "definition", item.definition,
        (item.definition.declared_effects as string[] | undefined) ?? [],
        "sv-" + (item.definition.name as string),
      ),
    );
  }
  seq.submit(
    makeEnvelopeTs(
      "operator", "proposal",
      {
        requests: [
          { verb: "write", args: ["answer", 42], outputs: ["o-42"] },
        ],
      },
      ["write"],
      "sv-p1",
    ),
  );
  const problems: string[] = [];
  if (!deepEq(seq.state.units, vectors.state.units)) {
    problems.push(
      `units ${canonical(seq.state.units as Json)} != recorded ${canonical(vectors.state.units as Json)}`,
    );
  }
  if (stateHash(seq.state) !== vectors.state.state_hash) {
    problems.push(
      `state_hash ${stateHash(seq.state)} != recorded ${vectors.state.state_hash}`,
    );
  }
  if (foldStateHash(seq.log.entries) !== vectors.state.state_hash) {
    problems.push("refolded state hash differs from recorded state_hash");
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "vectors.state",
    problems.length
      ? problems.join("; ")
      : `sequencer replay of the vector scenario yields units ${canonical(vectors.state.units as Json)} and state_hash ${vectors.state.state_hash}, live and refolded`,
  );
}

// --- vectors.senses: sense computation (spec §11.3) ---------------------------
// Mirrors tests/test_vectors.py::test_senses_vectors: fold each
// case's entries, recompute the sense at the subject, and compare
// the whole reading {value, method, as_of_seq} exactly.
{
  const problems: string[] = [];
  let cases = 0;
  for (const [sense, list] of Object.entries(vectors.senses)) {
    for (const c of list) {
      cases++;
      const state = fold(c.entries);
      let reading: SenseReading;
      try {
        reading = computeSense(`${sense}:${c.subject}`, c.entries, state);
      } catch (err) {
        problems.push(
          `${sense}:${c.subject}: threw ${(err as Error).message}`,
        );
        continue;
      }
      if (!deepEq(reading, c.expect)) {
        problems.push(
          `${sense}:${c.subject}: computed ${canonical(reading as unknown as Json)} != recorded ${canonical(c.expect as unknown as Json)}`,
        );
      }
      if (reading.as_of_seq !== c.entries[c.entries.length - 1].seq) {
        problems.push(`${sense}:${c.subject}: as_of_seq mismatch`);
      }
    }
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "vectors.senses",
    problems.length
      ? problems.join("; ")
      : `all ${cases} sense cases (contention + authority) recompute byte-identically, method strings included`,
  );
}

// --- vectors.anchor: Ed25519 checkpoint verification (spec §15) ---------------
// Mirrors tests/test_vectors.py::test_anchor_vector, and then runs
// the full section 15.5 procedure over the vector chain: the
// recorded checkpoint must VERIFY the rebuilt entries.
{
  const section = vectors.anchor;
  const envelope = section.envelope;
  const body = envelope.body as JsonObject;
  const problems: string[] = [];
  const derivedPub = ed25519PubFromSeed(section.test_seed);
  if (derivedPub !== envelope.pubkey) {
    problems.push(
      `pubkey derived from the recorded test seed is ${derivedPub}, envelope carries ${envelope.pubkey as string}`,
    );
  }
  const expectedBody = {
    format: "jacquard/anchor/1",
    log_id: vectors.entries[0].hash,
    label: "golden-vectors",
    checkpoint_seq: 0,
    log_length: 4,
    head_hash: vectors.entries[3].hash,
    spec: "jacquard/0.5",
    prev_checkpoint: null,
  };
  if (!deepEq(body, expectedBody)) {
    problems.push("checkpoint body differs from the expected body");
  }
  if (checkpointHash(body) !== section.checkpoint_hash) {
    problems.push(
      `checkpoint_hash ${checkpointHash(body)} != recorded ${section.checkpoint_hash}`,
    );
  }
  if (
    !ed25519Verify(
      envelope.pubkey as string,
      canonicalBytes(body as Json),
      envelope.sig as string,
    )
  ) {
    problems.push("signature does not verify over the body's canonical bytes");
  }
  const tampered = deepClone(body);
  tampered.log_length = 3;
  if (
    ed25519Verify(
      envelope.pubkey as string,
      canonicalBytes(tampered as Json),
      envelope.sig as string,
    )
  ) {
    problems.push("signature WRONGLY verifies over a tampered body");
  }
  const result = verifyAnchor(rebuiltEntries, [envelope], envelope.pubkey as string);
  if (
    result.outcome !== "verified" ||
    result.anchored_length !== 4 ||
    result.unanchored_tail !== 0 ||
    result.checkpoints_checked !== 1 ||
    !result.internal_chain_ok
  ) {
    problems.push(
      `section 15.5 over the vector chain: ${JSON.stringify(result)}`,
    );
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "vectors.anchor",
    problems.length
      ? problems.join("; ")
      : "test-key pubkey derives from the recorded seed, checkpoint hash recomputes, Ed25519 signature verifies (and fails over a tampered body), and the §15.5 procedure reports the vector chain verified, 4/4 anchored, tail 0",
  );
}

// --- h. shape signatures over both proof-run corpora (spec §12.1) -------------
// The committed comparison: signature-expectations.json is
// generated by the PYTHON learner (gen_signature_expectations.py)
// over every queued decision in docs/proof-run/kernel.jsonl and
// docs/proof-run-2/kernel.jsonl. Here the TS signature is
// recomputed for the same entries and compared item-for-item,
// plus the canonical hash of each corpus's item list.
{
  const problems: string[] = [];
  const details: string[] = [];
  try {
    const expectations = loadJson(
      join(here, "signature-expectations.json"),
    ) as {
      corpora: {
        path: string;
        entry_count: number;
        items: Json[];
        items_hash: string;
      }[];
    };
    for (const corpus of expectations.corpora) {
      const logPath = join(here, "..", "..", corpus.path);
      const lines = readFileSync(logPath, "utf8")
        .split("\n")
        .filter((l) => l.trim().length > 0);
      const entries = lines.map(
        (l) => JSON.parse(l) as StoredEntry,
      );
      if (entries.length !== corpus.entry_count) {
        problems.push(
          `${corpus.path}: ${entries.length} entries, fixture records ${corpus.entry_count}`,
        );
        continue;
      }
      const items: Json[] = [];
      for (const entry of entries) {
        const body = entry.body;
        if (entry.kind === "decision" && "requests" in body) {
          items.push({
            seq: entry.seq,
            proposal_id: (body.proposal_id ?? null) as Json,
            signature: shapeSignature(body.requests as Json[]),
          } as unknown as Json);
        }
      }
      if (!deepEq(items, corpus.items)) {
        problems.push(`${corpus.path}: item lists differ`);
        continue;
      }
      const h = hash(items as unknown as Json);
      if (h !== corpus.items_hash) {
        problems.push(
          `${corpus.path}: items hash ${h} != Python ${corpus.items_hash}`,
        );
        continue;
      }
      details.push(
        `${corpus.path}: ${items.length} queued decisions, items hash ${h} == Python`,
      );
    }
  } catch (err) {
    problems.push(`cannot run: ${(err as Error).message}`);
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "h. shape signatures (§12.1)",
    problems.length ? problems.join("; ") : details.join("; "),
  );
}

// --- i. token-form battery (spec §§4-5, slice 17 semantics) --------------------
// The Python adversarial battery's stock-kernel half
// (tests/test_quotation_battery.py), run against the TS
// dictionary: unknown dict forms are REFUSED(SPEC) with the form
// named, the walk accounts verbs through nesting and branches,
// literal values are data, and hybrid forms are refused.
{
  const problems: string[] = [];
  const submitDef = (seq: Sequencer, defn: JsonObject, id: string) =>
    seq.submit(makeEnvelopeTs("operator", "definition", defn, [], id));
  const sneaky: JsonObject = {
    name: "any-write",
    signature: { ins: ["list"], outs: ["bool"] },
    body: [
      {
        any: [
          "drop", { lit: "probe/sneaky" }, { lit: 1 }, "write",
          { lit: true },
        ],
      },
    ],
    examples: [
      { args: [[7]], expect: [true], requests: ["write"] },
    ],
  };
  {
    const seq = new Sequencer();
    const v = submitDef(seq, sneaky, "b-original");
    if (
      v.status !== "REFUSED" || v.refusal !== "SPEC" ||
      !(v.detail as string).includes("'any'") ||
      "any-write" in seq.state.dictionary
    ) {
      problems.push(`original probe case: ${JSON.stringify(v)}`);
    }
  }
  {
    const seq = new Sequencer();
    const nested: JsonObject = {
      name: "nested",
      signature: { ins: ["list"], outs: ["bool"] },
      body: [
        {
          any: [
            {
              any: [
                "drop", { lit: "u" }, { lit: 1 }, "write", { lit: true },
              ],
            },
          ],
        },
      ],
      examples: [],
    };
    if (!deepEq([...seq.dictionary.computedEffects(nested)].sort(), ["write"])) {
      problems.push("nested quotation: walk did not account 'write'");
    }
    const v = submitDef(seq, nested, "b-nested");
    if (v.status !== "REFUSED" || v.refusal !== "SPEC") {
      problems.push(`nested quotation: ${JSON.stringify(v)}`);
    }
    const branchy: JsonObject = {
      name: "branchy",
      signature: { ins: [], outs: ["bool"] },
      body: [
        { lit: true },
        {
          if: [
            {
              any: [
                "drop", { lit: "u" }, { lit: 1 }, "write", { lit: true },
              ],
            },
          ],
          else: [{ lit: false }],
        },
      ],
      examples: [],
    };
    if (!deepEq([...seq.dictionary.computedEffects(branchy)].sort(), ["write"])) {
      problems.push("if-branch quotation: walk did not account 'write'");
    }
    const v2 = submitDef(seq, branchy, "b-branch");
    if (v2.status !== "REFUSED" || v2.refusal !== "SPEC") {
      problems.push(`if-branch quotation: ${JSON.stringify(v2)}`);
    }
  }
  {
    const seq = new Sequencer();
    const inner: JsonObject = {
      name: "maybe-write",
      signature: { ins: ["bool"], outs: [] },
      body: [{ if: [{ lit: "u" }, { lit: 1 }, "write"] }],
      examples: [],
    };
    const v = submitDef(seq, inner, "b-inner");
    if (v.status !== "accepted" || !deepEq(v.computed_effects, ["write"])) {
      problems.push(`composition inner: ${JSON.stringify(v)}`);
    }
    const outer: JsonObject = {
      name: "outer",
      signature: { ins: ["bool"], outs: [] },
      body: ["maybe-write"],
      examples: [],
    };
    const v2 = submitDef(seq, outer, "b-outer");
    if (v2.status !== "accepted" || !deepEq(v2.computed_effects, ["write"])) {
      problems.push(`composition outer: ${JSON.stringify(v2)}`);
    }
  }
  {
    const seq = new Sequencer();
    const dataOnly: JsonObject = {
      name: "data-only",
      signature: { ins: [], outs: ["list"] },
      body: [{ lit: ["write", "send", { any: ["spend"] }] }],
      examples: [
        {
          args: [],
          expect: [["write", "send", { any: ["spend"] }]],
        },
      ],
    };
    const v = submitDef(seq, dataOnly, "b-data");
    if (v.status !== "accepted" || !deepEq(v.computed_effects, [])) {
      problems.push(`literal data: ${JSON.stringify(v)}`);
    } else {
      const [stack, requests] = seq.evaluateWord("data-only", "operator", []);
      if (
        !deepEq(stack, [["write", "send", { any: ["spend"] }]]) ||
        requests.length !== 0
      ) {
        problems.push("literal data: evaluation was not inert");
      }
    }
  }
  {
    const seq = new Sequencer();
    const hybridIf: JsonObject = {
      name: "hybrid-if",
      signature: { ins: [], outs: ["bool"] },
      body: [
        { lit: true },
        { if: [{ lit: true }], any: [{ lit: true }] },
      ],
      examples: [],
    };
    const v = submitDef(seq, hybridIf, "b-hybrid-if");
    if (v.status !== "REFUSED" || v.refusal !== "SPEC") {
      problems.push(`hybrid if: ${JSON.stringify(v)}`);
    }
    const hybridLit: JsonObject = {
      name: "hybrid-lit",
      signature: { ins: [], outs: ["int"] },
      body: [{ lit: 1, any: [] }],
      examples: [],
    };
    const v2 = submitDef(seq, hybridLit, "b-hybrid-lit");
    if (v2.status !== "REFUSED" || v2.refusal !== "SPEC") {
      problems.push(`hybrid lit: ${JSON.stringify(v2)}`);
    }
  }
  {
    const seq = new Sequencer();
    const stack: Json[] = [];
    const requests: JsonObject[] = [];
    let caught: Refusal | null = null;
    try {
      seq.dictionary.exec(
        [{ any: [{ lit: "u" }, { lit: 1 }, "write"] }] as Json[],
        stack, requests, seq.context("operator"), {},
      );
    } catch (err) {
      if (err instanceof Refusal) caught = err;
      else throw err;
    }
    if (!caught || caught.name !== "SPEC" || requests.length !== 0) {
      problems.push("forged body at evaluation was not REFUSED(SPEC)");
    }
  }
  report(
    problems.length ? "FAIL" : "PASS",
    "i. token-form battery (§§4–5)",
    problems.length
      ? problems.join("; ")
      : "unknown forms REFUSED(SPEC) by name (probe, nested, if-branch, both hybrids, forged-at-evaluation); composition unions effects; literal values stay data",
  );
}

process.exit(failures === 0 ? 0 : 1);
