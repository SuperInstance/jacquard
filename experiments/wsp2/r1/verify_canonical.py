#!/usr/bin/env python3
"""Phase 16 R1 (slice 44) — mechanical verifier for the
canonicalised E8 batteries.

Independently re-derives, from the ORIGINAL Phase 15 batteries
only, what every canonicalised item must look like under the
rules stated in canonicalise.py, and compares against the
builder's output files byte-for-byte.  The segmenter here is a
separate regex-based implementation (the builder walks an
expected-label sequence with str.find; this verifier splits on
anchored label boundaries and reassembles), so a parsing defect
in one implementation does not silently pass the other.

Checks, per item, both files:
  * id sequence identical to the original file (same items, same
    order, none added/dropped/duplicated);
  * every field except `context` and `split` identical to the
    original (gold, operator_correct, correct_outcome,
    correctness_evidence, source, order_ts, ts_basis,
    source_pointer) — content preservation of the annotations;
  * `context` exactly equal to the independently re-derived
    canonical rendering (segment equations per transform mode:
    identity / gpu enrich fold / board->kernel / jev->kernel).

Exit code 0 and "VERIFY PASS" only if every check passes.
Usage: verify_canonical.py ORIGINAL_DIR CANONICAL_DIR
"""
import json
import re
import sys
from pathlib import Path

NON_CONTEXT_FIELDS = ["id", "source", "order_ts", "ts_basis",
                      "gold", "operator_correct", "correct_outcome",
                      "correctness_evidence", "source_pointer"]
ENRICH = ["command shape", "job name", "uses"]


def seg_re(labels):
    """Regex segmenter: returns dict label->value or raises."""
    pat = None
    for lab in labels:
        piece = re.escape(lab) + r": (.*?)"
        pat = piece if pat is None else pat + r"(?:; " + piece + r")?"
        # optional groups only safe for enrich; handled by caller
    return pat


def split_seq(context, labels, optional=()):
    """Split by walking anchored boundaries: find each label at
    the current position; value runs to the next label boundary
    found by regex search over the remaining label set."""
    out = {}
    order = []
    s = context
    labs = list(labels)
    i = 0
    while i < len(labs):
        lab = labs[i]
        head = lab + ": "
        if not s.startswith(head):
            if lab in optional:
                i += 1
                continue
            raise ValueError("missing label %r near %r"
                             % (lab, s[:60]))
        s = s[len(head):]
        rest = labs[i + 1:]
        cut = None
        for j, later in enumerate(rest):
            m = re.search(r"; " + re.escape(later) + r": ", s)
            if m and (cut is None or m.start() < cut[0]):
                cut = (m.start(), later)
        if cut is None:
            out[lab] = s
            order.append(lab)
            s = ""
            i = len(labs)
        else:
            out[lab] = s[:cut[0]]
            order.append(lab)
            s = s[cut[0] + 2:]
            # advance i to the boundary label actually found
            i = labs.index(cut[1])
    if s:
        raise ValueError("unparsed tail %r" % s[:60])
    return out, order


KERNEL = ["producer", "class", "effects", "requests",
          "standing rule in force for this shape",
          "command shape", "job name", "uses", "policy facts"]
BOARD = ["producer", "effect", "resource", "start",
         "planned duration", "check-by", "task", "contention",
         "policy facts"]
SR = "standing rule in force for this shape"


def join(segs):
    return "; ".join("%s: %s" % kv for kv in segs)


def expected_heldout_canon(it):
    src, ctx = it["source"], it["context"]
    if src in ("board-shadow", "slice30-booking"):
        return ctx
    if src == "gpu-windows":
        d, _ = split_seq(ctx, KERNEL, optional=ENRICH)
        req = d["requests"] + "".join(
            "; %s: %s" % (lab, d[lab]) for lab in ENRICH
            if lab in d)
        return join([("producer", d["producer"]),
                     ("class", d["class"]),
                     ("effects", d["effects"]),
                     ("requests", req),
                     (SR, d[SR]),
                     ("policy facts", d["policy facts"])])
    raise ValueError("bad source %r" % src)


def expected_diag_cross(it):
    src, ctx = it["source"], it["context"]
    if src in ("proof-run", "proof-run-2"):
        return ctx
    if src == "board-shadow":
        d, _ = split_seq(ctx, BOARD)
        m = re.fullmatch(r"write booking/([^/;]+)/([^/;]+)",
                         d["effect"])
        if not m:
            raise ValueError("bad effect %r" % d["effect"])
        box, seat = m.groups()
        if d["resource"] != box + " seat " + seat:
            raise ValueError("effect/resource mismatch")
        req = ("write booking/%s/%s start %s; planned: %s; "
               "check-by: %s; task: %s; contention: %s"
               % (box, seat, d["start"], d["planned duration"],
                  d["check-by"], d["task"], d["contention"]))
        return join([("producer", d["producer"]),
                     ("class", "booking"),
                     ("effects", "write"),
                     ("requests", req),
                     (SR, "none recorded"),
                     ("policy facts", d["policy facts"])])
    if src == "jev":
        m = re.search(r"cases\(\): ([a-z0-9\-]+)",
                      it["source_pointer"]["locator"])
        if not m:
            raise ValueError("no jev class")
        return join([("producer", "not recorded"),
                     ("class", m.group(1)),
                     ("effects", "not recorded"),
                     ("requests", ctx),
                     (SR, "none recorded"),
                     ("policy facts", "none recorded")])
    raise ValueError("bad source %r" % src)


def load(p):
    return [json.loads(ln) for ln in
            Path(p).read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def check(orig_path, canon_path, expect_fn, failures):
    orig = load(orig_path)
    canon = load(canon_path)
    if len(orig) != len(canon):
        failures.append("%s: count %d != %d"
                        % (canon_path, len(canon), len(orig)))
        return 0
    npass = 0
    for o, c in zip(orig, canon):
        tag = "%s/%s" % (Path(canon_path).name, o["id"])
        if c["id"] != o["id"]:
            failures.append(tag + ": id order mismatch")
            continue
        ok = True
        for f in NON_CONTEXT_FIELDS:
            if c.get(f) != o.get(f):
                failures.append(tag + ": field %s differs" % f)
                ok = False
        try:
            want = expect_fn(o)
        except Exception as e:  # noqa: BLE001
            failures.append(tag + ": re-derivation failed: %s" % e)
            continue
        if c["context"] != want:
            failures.append(tag + ": context != re-derived "
                            "canonical rendering")
            ok = False
        if ok:
            npass += 1
    return npass


def main():
    orig_dir, canon_dir = Path(sys.argv[1]), Path(sys.argv[2])
    failures = []
    total = 0
    total += check(orig_dir / "heldout.jsonl",
                   canon_dir / "heldout_canonical.jsonl",
                   expected_heldout_canon, failures)
    total += check(orig_dir / "diagnostic.jsonl",
                   canon_dir / "diagnostic_crossformat.jsonl",
                   expected_diag_cross, failures)
    for f in failures:
        print("FAIL:", f)
    if failures:
        print("VERIFY FAIL (%d items passed, %d failures)"
              % (total, len(failures)))
        return 1
    print("VERIFY PASS (%d/%d items: every non-context field "
          "identical; every context exactly the re-derived "
          "canonical rendering)" % (total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
