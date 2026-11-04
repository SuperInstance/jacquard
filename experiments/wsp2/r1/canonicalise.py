#!/usr/bin/env python3
"""Phase 16 R1 (slice 44) — E8 format-era canonicalisation builder.

Reads the ORIGINAL Phase 15 E8 batteries (diagnostic.jsonl /
heldout.jsonl, as in experiments/wsp/e8/) and writes two
re-expressed batteries:

  heldout_canonical.jsonl     held-out items (n=53) re-expressed in
                              the diagnostic era's canonical format
  diagnostic_crossformat.jsonl diagnostic items (n=112) re-expressed
                              in a held-out-era format

Every non-context field is copied byte-for-byte; only the
`context` string is re-rendered, item by item, by the mechanical
rules below.  verify_canonical.py proves content preservation.

ERA FORMATS (from experiments/wsp/e8/curate.py, the single
renderer of both eras — see R1-AUTOPSY.md for the full
characterisation):

Diagnostic era renderers:
  D-board  board_items():  producer; effect; resource; start;
           planned duration; check-by; task; contention;
           policy facts   (9 labelled segments)
  D-kernel kernel_items() WITHOUT enrich:  producer; class;
           effects; requests; standing rule in force for this
           shape; policy facts   (6 labelled segments)
  D-jev    free prose paragraphs (jev_items())

Held-out era renderers:
  H-board  board_items() — the SAME function/output as D-board
  H-kernel kernel_items() WITH enrich (gpu-windows): enrich
           segments (command shape / job name / uses) INSERTED
           between the standing-rule segment and policy facts;
           plus kernel_items() without enrich but with era policy
           texts (slice30-booking)
  (no prose family exists in the held-out era)

CANONICALISATION (i) — held-out -> diagnostic canonical:
  board-shadow items: identity.  The diagnostic board renderer is
    byte-identical for both eras (one curate.py function), so a
    held-out board item is already in the diagnostic canonical
    board format.
  slice30-booking items: identity.  Already in the exact D-kernel
    6-segment form; its policy-facts TEXT differs from the
    diagnostic proof text, but policy text is content, not
    rendering, and is preserved verbatim.
  gpu-windows items: enrich segments are REMOVED as standalone
    segments and folded, in their original order and with their
    labels and values verbatim, onto the tail of the requests
    segment — yielding the exact D-kernel 6-segment form.
    (Diagnostic-era requests segments are where job-identifying
    detail lives: shell commands, write targets, booking specs.)

CANONICALISATION (ii) — diagnostic -> held-out-era format
(target = the H-kernel form, the only decision-log format the
held-out era uses; bookings in the held-out era are rendered in
kernel form too — cf. the slice30-booking source, whose booking
rows curate.py deduped against board items):
  proof-run / proof-run-2 items: identity (already H-kernel form;
    they carry no enrich content).
  board-shadow items: rendered in kernel form —
    producer <- board producer
    class    <- "booking" (the class curate.py's board sequencer
                submits for every board row)
    effects  <- "write" (first word of the board effect segment,
                whose remainder is the booking path)
    requests <- "write booking/<box>/<seat> start <start> UTC;
                planned: <planned duration>; check-by: <check-by>;
                task: <task>; contention: <contention>"
                — the render_requests() booking rendering used by
                curate.py for kernel-log bookings, with the board
                task and contention facts appended verbatim so no
                content is dropped
    standing rule in force for this shape <- "none recorded"
                (the board record carries no standing-rule fact;
                "none recorded" is curate.py's own placeholder
                convention)
    policy facts <- board policy facts, verbatim
    (<box>/<seat> are recovered from the board effect segment
    "write booking/<box>/<seat>".)
  jev items: rendered in kernel form —
    producer <- "not recorded", effects <- "not recorded",
    standing rule <- "none recorded",
    policy facts <- "none recorded"
                (jev prose carries no such labelled facts;
                placeholders follow curate.py's conventions)
    class    <- the case class recorded in the item's own
                source_pointer locator ("cases(): <class>")
    requests <- the item's full original prose context, verbatim

No gold, correctness, source, timestamp or pointer field is
touched in either direction.
"""
import json
import re
import sys
from pathlib import Path

KERNEL_LABELS = ["producer", "class", "effects", "requests",
                 "standing rule in force for this shape",
                 "command shape", "job name", "uses",
                 "policy facts"]
BOARD_LABELS = ["producer", "effect", "resource", "start",
                "planned duration", "check-by", "task",
                "contention", "policy facts"]
ENRICH_LABELS = ["command shape", "job name", "uses"]


def parse_segments(context, labels):
    """Split a labelled context into an ordered [(label, value)]
    list, walking the expected label sequence in order (so label-
    like text inside a value — e.g. '; check-by:' inside a kernel
    requests value — is not mistaken for a segment boundary).
    Raises ValueError on any deviation."""
    segs = []
    pos = 0
    remaining = list(labels)
    while remaining:
        lab = remaining.pop(0)
        prefix = ("" if pos == 0 else "; ") + lab + ": "
        if not context.startswith(prefix, pos):
            # optional labels (enrich) may be absent
            if lab in ENRICH_LABELS:
                continue
            raise ValueError("expected %r at %d in %r"
                             % (prefix, pos, context[:120]))
        start = pos + len(prefix)
        # value ends at the next expected label's boundary or EOS;
        # search for each later label, take the earliest hit
        end = len(context)
        for later in remaining:
            idx = context.find("; " + later + ": ", start)
            if idx != -1:
                end = min(end, idx)
        segs.append((lab, context[start:end]))
        pos = end
        if pos >= len(context):
            # drop trailing labels already consumed as boundaries
            break
    if pos != len(context):
        raise ValueError("trailing unparsed text at %d: %r"
                         % (pos, context[pos:pos + 80]))
    return segs


def render(segs):
    return "; ".join("%s: %s" % (lab, val) for lab, val in segs)


def segdict(segs):
    d = {}
    for lab, val in segs:
        if lab in d:
            raise ValueError("duplicate label %r" % lab)
        d[lab] = val
    return d


# ---------------- (i) held-out -> diagnostic canonical ------------

def canon_heldout(item):
    src = item["source"]
    ctx = item["context"]
    if src in ("board-shadow", "slice30-booking"):
        return ctx, "identity"
    if src == "gpu-windows":
        segs = parse_segments(ctx, KERNEL_LABELS)
        d = segdict(segs)
        enrich = [(lab, d[lab]) for lab in ENRICH_LABELS
                  if lab in d]
        if not enrich:
            raise ValueError("%s: gpu item without enrich"
                             % item["id"])
        new_requests = d["requests"] + "".join(
            "; %s: %s" % (lab, val) for lab, val in enrich)
        out = [("producer", d["producer"]),
               ("class", d["class"]),
               ("effects", d["effects"]),
               ("requests", new_requests),
               ("standing rule in force for this shape",
                d["standing rule in force for this shape"]),
               ("policy facts", d["policy facts"])]
        return render(out), "gpu-enrich-folded-into-requests"
    raise ValueError("unknown held-out source %r" % src)


# ---------------- (ii) diagnostic -> held-out-era format ----------

def cross_diagnostic(item):
    src = item["source"]
    ctx = item["context"]
    if src in ("proof-run", "proof-run-2"):
        return ctx, "identity"
    if src == "board-shadow":
        segs = parse_segments(ctx, BOARD_LABELS)
        d = segdict(segs)
        m = re.fullmatch(r"write booking/([^/;]+)/([^/;]+)",
                         d["effect"])
        if not m:
            raise ValueError("%s: unparsable board effect %r"
                             % (item["id"], d["effect"]))
        box, seat = m.group(1), m.group(2)
        # resource segment must agree with effect (content check)
        if d["resource"] != "%s seat %s" % (box, seat):
            raise ValueError("%s: effect/resource disagree"
                             % item["id"])
        requests = ("write booking/%s/%s start %s; planned: %s; "
                    "check-by: %s; task: %s; contention: %s"
                    % (box, seat, d["start"],
                       d["planned duration"], d["check-by"],
                       d["task"], d["contention"]))
        out = [("producer", d["producer"]),
               ("class", "booking"),
               ("effects", "write"),
               ("requests", requests),
               ("standing rule in force for this shape",
                "none recorded"),
               ("policy facts", d["policy facts"])]
        return render(out), "board-rendered-in-kernel-form"
    if src == "jev":
        loc = item["source_pointer"]["locator"]
        m = re.search(r"cases\(\): ([a-z0-9\-]+)", loc)
        if not m:
            raise ValueError("%s: no jev class in locator %r"
                             % (item["id"], loc))
        out = [("producer", "not recorded"),
               ("class", m.group(1)),
               ("effects", "not recorded"),
               ("requests", ctx),
               ("standing rule in force for this shape",
                "none recorded"),
               ("policy facts", "none recorded")]
        return render(out), "jev-prose-rendered-in-kernel-form"
    raise ValueError("unknown diagnostic source %r" % src)


def main():
    here = Path(__file__).resolve().parent
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else here
    held = [json.loads(ln) for ln in
            (src_dir / "heldout.jsonl").read_text(
                encoding="utf-8").splitlines() if ln.strip()]
    diag = [json.loads(ln) for ln in
            (src_dir / "diagnostic.jsonl").read_text(
                encoding="utf-8").splitlines() if ln.strip()]
    jobs = [(held, canon_heldout, "heldout_canonical.jsonl",
             "heldout-canonical"),
            (diag, cross_diagnostic, "diagnostic_crossformat.jsonl",
             "diagnostic-crossformat")]
    for items, fn, out_name, split_name in jobs:
        modes = {}
        with (here / out_name).open("w", encoding="utf-8") as fh:
            for it in items:
                new_ctx, mode = fn(it)
                modes[mode] = modes.get(mode, 0) + 1
                out = dict(it)
                out["context"] = new_ctx
                out["split"] = split_name
                fh.write(json.dumps(out, ensure_ascii=False) + "\n")
        print("%s: n=%d modes=%s" % (out_name, len(items), modes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
