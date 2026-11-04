// Cross-language drill, TypeScript side (slice 19).
//
// Drives fixture.json through the TS Sequencer port and writes
// the resulting log (canonical lines, exactly the Log file
// form) plus the canonical JSON of every op's verdict.
// Usage: node run_ts.ts <fixture> <log-out> <verdicts-out>

import { readFileSync, writeFileSync } from "node:fs";

import {
  SPEC_SEAL,
  canonical,
  type Json,
  type JsonObject,
} from "../jacquard.ts";
import { Log, Sequencer, envelopeHash } from "../kernel.ts";

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

const [fixturePath, logOut, verdictsOut] = process.argv.slice(2);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8")) as {
  ops: JsonObject[];
};
let seq = new Sequencer();
const hashes: { [idem: string]: string } = {};
const verdicts: Json[] = [];

for (const op of fixture.ops) {
  const kind = op.op as string;
  if (kind === "define") {
    const env = makeEnvelopeTs(
      op.producer as string, "definition", op.definition as Json, [],
      op.idem as string,
    );
    hashes[op.idem as string] = envelopeHash(env);
    verdicts.push(seq.submit(env) as Json);
  } else if (kind === "proposal") {
    const env = makeEnvelopeTs(
      op.producer as string, "proposal", op.body as Json,
      op.declared as string[], op.idem as string,
    );
    hashes[op.idem as string] = envelopeHash(env);
    verdicts.push(seq.submit(env) as Json);
  } else if (kind === "release") {
    verdicts.push(
      seq.releaseQueued(
        hashes[op.of as string], op.by as string,
        (op.reason as string | undefined) ?? undefined,
      ) as Json,
    );
  } else if (kind === "reject") {
    verdicts.push(
      seq.rejectQueued(
        hashes[op.of as string], op.by as string,
        (op.reason as string | undefined) ?? undefined,
      ) as Json,
    );
  } else if (kind === "expire") {
    verdicts.push(
      seq.expireQueued(
        hashes[op.of as string], op.by as string,
        (op.reason as string | undefined) ?? undefined,
      ) as Json,
    );
  } else if (kind === "grant") {
    verdicts.push(
      seq.grantBudget(op.producer as string, op.amount as number) as Json,
    );
  } else if (kind === "price") {
    verdicts.push(
      seq.postPrice(op.resource as string, op.price as number) as Json,
    );
  } else if (kind === "sense") {
    const entry = seq.submitSense(
      op.name as string, op.value as Json, op.producer as string,
    );
    verdicts.push({ entry: entry.hash });
  } else if (kind === "checkpoint") {
    const entry = seq.checkpoint(op.name as string);
    verdicts.push({ entry: entry.hash });
  } else if (kind === "standing") {
    seq.setStanding(op.producer as string, op.standing as JsonObject);
    verdicts.push({ standing: "set" });
  } else if (kind === "restart") {
    // A fresh sequencer over the same entries: the
    // cross-process shape (spec 0.7 section 3.1). Standing
    // and other constructor state do NOT survive; recorded
    // verdicts do.
    const saved = JSON.parse(JSON.stringify(seq.log.entries));
    seq = new Sequencer(new Log(saved));
    verdicts.push({ restarted_entries: saved.length });
  } else if (kind === "append_rule") {
    const entry = seq.log.append("rule", {
      producer: "learner", rule: op.rule as JsonObject,
    });
    seq.refold();
    verdicts.push({ appended: entry.hash });
  } else {
    throw new Error(`unknown op: ${kind}`);
  }
}

writeFileSync(logOut, seq.log.serialise());
writeFileSync(verdictsOut, canonical(verdicts as Json) + "\n");
console.log(
  `ts: ${seq.log.entries.length} entries, ${verdicts.length} verdicts`,
);
