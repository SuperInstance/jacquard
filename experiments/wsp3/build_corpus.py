#!/usr/bin/env python3
"""W1 corpus builder — Phase 17 shadow.

Mines the FULL git history of the agent-inbox repo (every version
of every file under inbox/, claimed/, done/, verdicts/, standing/
across all commits reachable from --all), deduplicates by content,
and emits corpus.jsonl: {id, text, provenance{commit, path, date}}.

Deterministic: commits visited in `git log --all` order sorted by
(commit date, commit hash); within a commit, paths sorted. The
first occurrence of a content hash wins its provenance.

Inclusion rules (stated in W1-CORPUS.md):
- blob must decode as strict UTF-8 and contain no NUL (text only);
- stripped text length must be in [20, 20000] chars;
- .gitkeep / empty blobs excluded by the length rule.
Excluded counts are printed as JSON at the end.
"""
import hashlib, json, subprocess, sys
from pathlib import Path

REPO = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "agent-inbox")
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/w1/corpus.jsonl"
DIRS = ("inbox", "claimed", "done", "verdicts", "standing")
MINLEN, MAXLEN = 1, 10**9

def git(*args):
    return subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True, check=True).stdout

# all commits, deterministic order: date then hash
raw = git("log", "--all", "--format=%H%x09%aI")
commits = []
for ln in raw.splitlines():
    if ln.strip():
        h, d = ln.split("\t")
        commits.append((d, h))
commits.sort()
date_of = {h: d for d, h in commits}
print(f"commits reachable from --all: {len(commits)}", file=sys.stderr)

seen = {}          # content sha -> corpus id
items = []
stats = {"blobs_seen": 0, "binary_skip": 0, "short_skip": 0,
         "long_skip": 0, "dup_skip": 0, "kept": 0}
blob_cache = {}

for date, commit in commits:
    tree = git("ls-tree", "-r", commit, "--", *DIRS)
    entries = []
    for ln in tree.splitlines():
        meta, path = ln.split("\t")
        parts = meta.split()
        if parts[1] != "blob":
            continue
        entries.append((path, parts[2]))
    entries.sort()
    for path, blob in entries:
        stats["blobs_seen"] += 1
        if blob not in blob_cache:
            data = subprocess.run(
                ["git", "-C", REPO, "cat-file", "-p", blob],
                capture_output=True, check=True).stdout
            blob_cache[blob] = data
        data = blob_cache[blob]
        if b"\x00" in data:
            stats["binary_skip"] += 1
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            stats["binary_skip"] += 1
            continue
        text = text.strip()
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if sha in seen:
            stats["dup_skip"] += 1
            continue
        if len(text) < MINLEN:
            stats["short_skip"] += 1
            continue
        if len(text) > MAXLEN:
            stats["long_skip"] += 1
            continue
        seen[sha] = True
        cid = f"c{len(items)+1:04d}"
        items.append({"id": cid, "text": text,
                      "provenance": {"commit": commit, "path": path,
                                     "date": date},
                      "sha256": sha})
        stats["kept"] += 1

Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with Path(OUT).open("w", encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")
print(json.dumps({"stats": stats, "n_items": len(items)}, indent=2))
