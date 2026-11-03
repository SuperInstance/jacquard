"""Cross-language drill orchestrator (slice 19; extended to
three kernels by slice 20).

Runs fixture.json through ALL THREE sequencers — the Python
reference (run_python.py), the TypeScript port (run_ts.ts) and
the Rust port (the `jacquard-cross-drill` binary from the
repo's rust/ tree, built here with cargo) — and compares the
three logs byte-for-byte and the three verdict streams
byte-for-byte. Writes EVIDENCE.txt with the stream size and
the sha256 of each artifact. Exit 0 iff every comparison is
exact.

    python3 conformance/ts/cross-drill/cross_drill.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
FIXTURE = os.path.join(HERE, "fixture.json")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def rust_binary():
    """Build (once per run) and locate the Rust drill binary."""
    manifest = os.path.join(ROOT, "rust", "Cargo.toml")
    cargo = shutil.which("cargo") or os.path.expanduser(
        os.path.join("~", ".cargo", "bin", "cargo"))
    subprocess.run(
        [cargo, "build", "--release", "--manifest-path", manifest,
         "--bin", "jacquard-cross-drill"],
        check=True, stdout=subprocess.DEVNULL)
    return os.path.join(
        ROOT, "rust", "target", "release", "jacquard-cross-drill")


def main():
    py_log = os.path.join(HERE, "python.jsonl")
    py_verdicts = os.path.join(HERE, "python-verdicts.json")
    ts_log = os.path.join(HERE, "ts.jsonl")
    ts_verdicts = os.path.join(HERE, "ts-verdicts.json")
    rs_log = os.path.join(HERE, "rust.jsonl")
    rs_verdicts = os.path.join(HERE, "rust-verdicts.json")
    subprocess.run([sys.executable, os.path.join(HERE, "run_python.py"),
                    FIXTURE, py_log, py_verdicts], check=True)
    subprocess.run(["node", os.path.join(HERE, "run_ts.ts"),
                    FIXTURE, ts_log, ts_verdicts], check=True)
    subprocess.run([rust_binary(), FIXTURE, rs_log, rs_verdicts],
                   check=True)
    logs = {name: read_bytes(path) for name, path in
            (("python", py_log), ("ts", ts_log), ("rust", rs_log))}
    verdicts = {name: read_bytes(path) for name, path in
                (("python", py_verdicts), ("ts", ts_verdicts),
                 ("rust", rs_verdicts))}
    entries = logs["python"].count(b"\n")
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        ops = json.load(fh)["ops"]
    logs_identical = len(set(logs.values())) == 1
    verdicts_identical = len(set(verdicts.values())) == 1
    lines = [
        "cross-language drill (slice 19; three kernels since "
        "slice 20) — fixture.json driven through all three "
        "sequencers",
        "ops in stream: %d" % len(ops),
        "log entries: %d" % entries,
        "python log sha256: %s" % hashlib.sha256(logs["python"]).hexdigest(),
        "ts     log sha256: %s" % hashlib.sha256(logs["ts"]).hexdigest(),
        "rust   log sha256: %s" % hashlib.sha256(logs["rust"]).hexdigest(),
        "logs byte-identical (all three): %s" % logs_identical,
        "python verdicts sha256: %s" % hashlib.sha256(verdicts["python"]).hexdigest(),
        "ts     verdicts sha256: %s" % hashlib.sha256(verdicts["ts"]).hexdigest(),
        "rust   verdicts sha256: %s" % hashlib.sha256(verdicts["rust"]).hexdigest(),
        "verdicts byte-identical (all three): %s" % verdicts_identical,
    ]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "EVIDENCE.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    return 0 if (logs_identical and verdicts_identical) else 1


if __name__ == "__main__":
    raise SystemExit(main())
