"""The append-only, hash-chained log (SPEC section 2).

State is a fold of the log. The log is never rewritten; a chain
that fails verification is refused, not repaired.
"""
import json
import os

from .canonical import SPEC_VERSION, canonical, hash_of

GENESIS_PREV = "0" * 64
ENTRY_KINDS = ("proposal", "decision", "definition", "execution",
               "sense", "checkpoint")


class Log:
    def __init__(self, path=None):
        self.path = path
        self.entries = []
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))
            if not self.verify_chain():
                raise ValueError("log at %s fails chain verification" % path)

    def append(self, kind, body):
        if kind not in ENTRY_KINDS:
            raise ValueError("unknown entry kind: %r" % (kind,))
        prev = self.entries[-1]["hash"] if self.entries else GENESIS_PREV
        entry = {"seq": len(self.entries), "prev": prev, "kind": kind,
                 "body": body, "spec": SPEC_VERSION}
        entry["hash"] = hash_of(entry)
        self.entries.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(canonical(entry).decode("utf-8") + "\n")
        return entry

    def verify_chain(self):
        prev = GENESIS_PREV
        for i, entry in enumerate(self.entries):
            if entry.get("seq") != i or entry.get("prev") != prev:
                return False
            body = {k: entry[k] for k in ("seq", "prev", "kind", "body", "spec")}
            if hash_of(body) != entry.get("hash"):
                return False
            prev = entry["hash"]
        return True
