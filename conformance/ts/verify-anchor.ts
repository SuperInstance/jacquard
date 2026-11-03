// verify-anchor — the TS port of tools/jqanchor.py's verify
// verb (spec 15.5), over the section 15 verifier in kernel.ts.
//
//   node verify-anchor.ts <log.jsonl> --checkpoints <dir> --pubkey <hex>
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
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--checkpoints") checkpointsDir = args[++i];
  else if (args[i] === "--pubkey") pubkey = args[++i];
}
if (!logPath || !checkpointsDir || !pubkey) {
  console.error(
    "usage: node verify-anchor.ts <log.jsonl> --checkpoints <dir> --pubkey <hex>",
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
    else if (name.endsWith(".json")) out.push(path);
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

const result = verifyAnchor(entries, envelopes, pubkey);
console.log(JSON.stringify(result, null, 1));
process.exit(
  result.outcome === "failed"
    ? 1
    : result.outcome === "unanchored"
      ? 3
      : 0,
);
