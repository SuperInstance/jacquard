"""Cross-language drill orchestrator (slice 19).

Runs fixture.json through BOTH sequencers — the Python
reference (run_python.py) and the TypeScript port (run_ts.ts) —
and compares the two logs byte-for-byte and the two verdict
streams byte-for-byte. Writes EVIDENCE.txt with the stream
size and the sha256 of each artifact. Exit 0 iff both
comparisons are exact.

    python3 conformance/ts/cross-drill/cross_drill.py
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixture.json")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    py_log = os.path.join(HERE, "python.jsonl")
    py_verdicts = os.path.join(HERE, "python-verdicts.json")
    ts_log = os.path.join(HERE, "ts.jsonl")
    ts_verdicts = os.path.join(HERE, "ts-verdicts.json")
    subprocess.run([sys.executable, os.path.join(HERE, "run_python.py"),
                    FIXTURE, py_log, py_verdicts], check=True)
    subprocess.run(["node", os.path.join(HERE, "run_ts.ts"),
                    FIXTURE, ts_log, ts_verdicts], check=True)
    with open(py_log, "rb") as fh:
        py_bytes = fh.read()
    with open(ts_log, "rb") as fh:
        ts_bytes = fh.read()
    with open(py_verdicts, "rb") as fh:
        py_v = fh.read()
    with open(ts_verdicts, "rb") as fh:
        ts_v = fh.read()
    entries = py_bytes.count(b"\n")
    ops = py_v and __import__("json").loads(
        open(FIXTURE, "r", encoding="utf-8").read())["ops"]
    lines = [
        "cross-language drill (slice 19) — fixture.json driven "
        "through both sequencers",
        "ops in stream: %d" % len(ops),
        "log entries: %d" % entries,
        "python log sha256: %s" % hashlib.sha256(py_bytes).hexdigest(),
        "ts     log sha256: %s" % hashlib.sha256(ts_bytes).hexdigest(),
        "logs byte-identical: %s" % (py_bytes == ts_bytes),
        "python verdicts sha256: %s" % hashlib.sha256(py_v).hexdigest(),
        "ts     verdicts sha256: %s" % hashlib.sha256(ts_v).hexdigest(),
        "verdicts byte-identical: %s" % (py_v == ts_v),
    ]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "EVIDENCE.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    return 0 if (py_bytes == ts_bytes and py_v == ts_v) else 1


if __name__ == "__main__":
    raise SystemExit(main())
