"""Cross-language drill, Python side (slice 19).

Drives fixture.json through the Python reference Sequencer and
writes the resulting log (canonical lines, exactly the Log file
form) plus the canonical JSON of every op's verdict.
Usage: python3 run_python.py <fixture> <log-out> <verdicts-out>
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from jacquard import Log, Sequencer, envelope_hash, make_envelope  # noqa: E402
from jacquard.canonical import canonical  # noqa: E402


def main():
    fixture_path, log_out, verdicts_out = sys.argv[1:4]
    with open(fixture_path, "r", encoding="utf-8") as fh:
        fixture = json.load(fh)
    seq = Sequencer()
    hashes = {}
    verdicts = []
    for op in fixture["ops"]:
        kind = op["op"]
        if kind == "define":
            env = make_envelope(op["producer"], "definition",
                                op["definition"], [], op["idem"])
            hashes[op["idem"]] = envelope_hash(env)
            verdicts.append(seq.submit(env))
        elif kind == "proposal":
            env = make_envelope(op["producer"], "proposal", op["body"],
                                op["declared"], op["idem"])
            hashes[op["idem"]] = envelope_hash(env)
            verdicts.append(seq.submit(env))
        elif kind == "release":
            verdicts.append(seq.release_queued(hashes[op["of"]], op["by"],
                                               op.get("reason")))
        elif kind == "reject":
            verdicts.append(seq.reject_queued(hashes[op["of"]], op["by"],
                                              op.get("reason")))
        elif kind == "expire":
            verdicts.append(seq.expire_queued(hashes[op["of"]], op["by"],
                                              op.get("reason")))
        elif kind == "grant":
            verdicts.append(seq.grant_budget(op["producer"], op["amount"]))
        elif kind == "price":
            verdicts.append(seq.post_price(op["resource"], op["price"]))
        elif kind == "sense":
            entry = seq.submit_sense(op["name"], op["value"], op["producer"])
            verdicts.append({"entry": entry["hash"]})
        elif kind == "checkpoint":
            entry = seq.checkpoint(op["name"])
            verdicts.append({"entry": entry["hash"]})
        elif kind == "standing":
            seq.set_standing(op["producer"], op["standing"])
            verdicts.append({"standing": "set"})
        elif kind == "restart":
            # A fresh sequencer over the same entries: the
            # cross-process shape (spec 0.7 section 3.1).
            # Standing and other constructor state do NOT
            # survive; recorded verdicts do.
            saved = copy.deepcopy(seq.log.entries)
            new_log = Log()
            new_log.entries = saved
            seq = Sequencer(new_log)
            verdicts.append({"restarted_entries": len(saved)})
        elif kind == "append_rule":
            entry = seq.log.append("rule", {"producer": "learner",
                                            "rule": op["rule"]})
            seq._refold()
            verdicts.append({"appended": entry["hash"]})
        else:
            raise ValueError("unknown op: %r" % (kind,))
    with open(log_out, "wb") as fh:
        for entry in seq.log.entries:
            fh.write(canonical(entry) + b"\n")
    with open(verdicts_out, "wb") as fh:
        fh.write(canonical(verdicts) + b"\n")
    print("python: %d entries, %d verdicts"
          % (len(seq.log.entries), len(verdicts)))


if __name__ == "__main__":
    main()
