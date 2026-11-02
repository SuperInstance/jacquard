// Jacquard conformance runner — Phase 3 slice 8 (TypeScript, spec-only).
//
// Run from this directory:  node check.ts
// Prints one PASS/FAIL line per check (a–f), SKIP lines for the vector
// sections that encode dictionary evaluation / sequencer execution (out of
// this slice's fold scope), and exits non-zero on any FAIL.

import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  SPEC_SEAL,
  entryHash,
  envelopeId,
  fold,
  foldStateHash,
  makeEntry,
  stateHash,
  validateEnvelope,
  verifyChain,
  type Envelope,
  type Json,
  type StoredEntry,
} from "./jacquard.ts";

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
  definitions: unknown[];
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
// "jacquard-spec/0.2") must equal the seal recorded in vectors.json.
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
// prev chain and spec "jacquard/0.2"; each must reproduce its recorded hash,
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

// --- out-of-scope vector sections --------------------------------------------
report(
  "SKIP",
  "vectors.definitions",
  "encodes dictionary evaluation and computed effects (spec §5), outside this fold-scope implementation",
);
report(
  "SKIP",
  "vectors.state",
  "encodes sequencer execution of the vector envelope (spec §7), outside this fold-scope implementation",
);

process.exit(failures === 0 ? 0 : 1);
