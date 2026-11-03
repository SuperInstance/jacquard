// verify-anchor — the TS port of tools/jqanchor.py's verify
// verb (spec 15.5), over the section 15 verifier in kernel.ts.
//
//   node verify-anchor.ts <log.jsonl> --checkpoints <dir> --pubkey <hex>
//   node verify-anchor.ts <log.jsonl> --checkpoints <dir> --keys <registry>
//
// --keys reads the witness key registry (spec 15.3) from a
// keys.json file or a transport directory holding one, and builds
// the pinned schedule for the presented log's id — the TS twin of
// jqanchor verify --keys. Both registry grammars are accepted,
// each read under its own rule: jacquard/anchor-keys/1 under the
// legacy reading (every key participates in every log's schedule,
// an omitted side unbounded) and jacquard/anchor-keys/2 with null
// windows (a log_id omitted from BOTH of a key's maps means that
// key signs nothing for that log and contributes no interval to
// its schedule). Any other format is refused by name.
//
// Prints the result as JSON (the same eight fields as the
// Python tool) and exits 0 for verified / verified_to_anchor,
// 1 for failed, 3 for unanchored, 2 for tool refusal.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import type { JsonObject, StoredEntry } from "./jacquard.ts";
import { verifyAnchor } from "./kernel.ts";

const args = process.argv.slice(2);
const logPath = args[0];
let checkpointsDir: string | null = null;
let pubkey: string | null = null;
let keysPath: string | null = null;
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--checkpoints") checkpointsDir = args[++i];
  else if (args[i] === "--pubkey") pubkey = args[++i];
  else if (args[i] === "--keys") keysPath = args[++i];
}
if (!logPath || !checkpointsDir || (!pubkey && !keysPath)) {
  console.error(
    "usage: node verify-anchor.ts <log.jsonl> --checkpoints <dir> (--pubkey <hex> | --keys <registry>)",
  );
  process.exit(2);
}

const entries: StoredEntry[] = readFileSync(logPath, "utf8")
  .split("\n")
  .filter((l) => l.trim().length > 0)
  .map((l) => JSON.parse(l) as StoredEntry);

function collectJson(dir: string, out: string[]): void {
  for (const name of readdirSync(dir).sort()) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) collectJson(path, out);
    else if (name.endsWith(".json") && name !== "keys.json") out.push(path);
  }
}

const files: string[] = [];
collectJson(checkpointsDir, files);
const envelopes: JsonObject[] = [];
const problems: string[] = [];
for (const file of files) {
  try {
    const env = JSON.parse(readFileSync(file, "utf8")) as JsonObject;
    const keys = Object.keys(env).sort();
    if (
      keys.length !== 3 ||
      keys[0] !== "body" || keys[1] !== "pubkey" || keys[2] !== "sig"
    ) {
      problems.push(`${file}: not a checkpoint envelope`);
      continue;
    }
    envelopes.push(env);
  } catch (err) {
    problems.push(`${file}: ${(err as Error).message}`);
  }
}

if (problems.length) {
  console.log(
    JSON.stringify(
      {
        outcome: "failed",
        failure: {
          stage: "history",
          checkpoint_seq: null,
          detail: `checkpoint store problems: ${problems.join("; ")}`,
        },
      },
      null,
      1,
    ),
  );
  process.exit(1);
}

let schedule: [number, string][] | undefined;
let pinned = pubkey;
if (keysPath) {
  const registryFile = statSync(keysPath).isDirectory()
    ? join(keysPath, "keys.json")
    : keysPath;
  const registry = JSON.parse(readFileSync(registryFile, "utf8")) as {
    format?: string;
    keys?: {
      pubkey: string;
      signs_from?: Record<string, unknown>;
      signs_until?: Record<string, unknown>;
    }[];
  };
  if (
    (registry.format !== "jacquard/anchor-keys/1" &&
      registry.format !== "jacquard/anchor-keys/2") ||
    !registry.keys
  ) {
    console.error(
      `${registryFile}: not a jacquard/anchor-keys/1 or jacquard/anchor-keys/2 registry`,
    );
    process.exit(2);
  }
  const logId = entries.length ? (entries[0].hash as string) : "0".repeat(64);
  // Spec 15.3 schedule derivation, mirroring the Python
  // schedule_from_registry: under /2 a key naming the log in
  // neither map holds a null window and is skipped; under /1 (and
  // for a one-sided omission under /2) an omitted side is
  // unbounded — from defaults to 0, until to open-ended.
  const nullWindows = registry.format === "jacquard/anchor-keys/2";
  const intervals: { from: number; until: number | null; pubkey: string }[] = [];
  for (const k of registry.keys) {
    const hasFrom =
      k.signs_from != null &&
      Object.prototype.hasOwnProperty.call(k.signs_from, logId);
    const hasUntil =
      k.signs_until != null &&
      Object.prototype.hasOwnProperty.call(k.signs_until, logId);
    if (nullWindows && !hasFrom && !hasUntil) continue;
    const from: unknown = hasFrom ? k.signs_from![logId] : 0;
    const until: unknown = hasUntil ? k.signs_until![logId] : null;
    if (
      typeof from !== "number" || !Number.isInteger(from) || from < 0 ||
      (until !== null &&
        (typeof until !== "number" || !Number.isInteger(until) ||
          until < (from as number)))
    ) {
      console.error(
        `key registry window for log ${logId} is malformed: ${JSON.stringify(k)}`,
      );
      process.exit(2);
    }
    intervals.push({
      from: from as number,
      until: until as number | null,
      pubkey: k.pubkey,
    });
  }
  intervals.sort((a, b) => a.from - b.from);
  if (!intervals.length || intervals[0].from !== 0) {
    console.error(
      `key registry does not cover checkpoint_seq 0 for log ${logId}`,
    );
    process.exit(2);
  }
  for (let i = 1; i < intervals.length; i++) {
    if (intervals[i - 1].until === null || intervals[i].from !== intervals[i - 1].until! + 1) {
      console.error(
        `key registry windows for log ${logId} do not partition its checkpoint sequence (gap or overlap after seq ${intervals[i - 1].until})`,
      );
      process.exit(2);
    }
  }
  schedule = intervals.map((iv) => [iv.from, iv.pubkey] as [number, string]);
  pinned = schedule[0][1];
}

const result = verifyAnchor(entries, envelopes, pinned!, schedule);
console.log(JSON.stringify(result, null, 1));
process.exit(
  result.outcome === "failed"
    ? 1
    : result.outcome === "unanchored"
      ? 3
      : 0,
);
