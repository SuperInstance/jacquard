"""Cross-language drill orchestrator (slice 19; extended to
three kernels by slice 20; second fixture by slice 38).

Runs each fixture through ALL THREE sequencers — the Python
reference (run_python.py), the TypeScript port (run_ts.ts)
and the Rust port (the `jacquard-cross-drill` binary from
the repo's rust/ tree, built here with cargo) — and compares
the three logs byte-for-byte and the three verdict streams
byte-for-byte. Writes EVIDENCE.txt with the stream sizes and
the sha256 of every artifact. Exit 0 iff every comparison
is exact.

    python3 conformance/ts/cross-drill/cross_drill.py

Fixtures:
- fixture.json — the original 38-op stream (slices 19/20).
- fixture-resubmission.json — the spec 0.7 section 3.1
  stream (slice 38): duplicate submissions of every shape
  across `restart` ops (a fresh sequencer over the same
  entries — the cross-process shape the adapters have),
  including a resubmission after an operator release.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

FIXTURES = [
    ("fixture.json", ""),
    ("fixture-resubmission.json", "-resubmission"),
]


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


def run_fixture(rust_bin, fixture_name, suffix):
    fixture = os.path.join(HERE, fixture_name)
    py_log = os.path.join(HERE, "python%s.jsonl" % suffix)
    py_verdicts = os.path.join(HERE, "python%s-verdicts.json" % suffix)
    ts_log = os.path.join(HERE, "ts%s.jsonl" % suffix)
    ts_verdicts = os.path.join(HERE, "ts%s-verdicts.json" % suffix)
    rs_log = os.path.join(HERE, "rust%s.jsonl" % suffix)
    rs_verdicts = os.path.join(HERE, "rust%s-verdicts.json" % suffix)
    subprocess.run([sys.executable, os.path.join(HERE, "run_python.py"),
                    fixture, py_log, py_verdicts], check=True)
    subprocess.run(["node", os.path.join(HERE, "run_ts.ts"),
                    fixture, ts_log, ts_verdicts], check=True)
    subprocess.run([rust_bin, fixture, rs_log, rs_verdicts],
                   check=True)
    logs = {name: read_bytes(path) for name, path in
            (("python", py_log), ("ts", ts_log), ("rust", rs_log))}
    verdicts = {name: read_bytes(path) for name, path in
                (("python", py_verdicts), ("ts", ts_verdicts),
                 ("rust", rs_verdicts))}
    entries = logs["python"].count(b"\n")
    with open(fixture, "r", encoding="utf-8") as fh:
        ops = json.load(fh)["ops"]
    logs_identical = len(set(logs.values())) == 1
    verdicts_identical = len(set(verdicts.values())) == 1
    lines = [
        "fixture: %s" % fixture_name,
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
    return lines, logs_identical and verdicts_identical


def main():
    rust_bin = rust_binary()
    lines = [
        "cross-language drill (slice 19; three kernels since "
        "slice 20; resubmission fixture since slice 38)",
    ]
    ok = True
    for fixture_name, suffix in FIXTURES:
        section, fixture_ok = run_fixture(rust_bin, fixture_name, suffix)
        lines.append("")
        lines.extend(section)
        ok = ok and fixture_ok
    text = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "EVIDENCE.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
