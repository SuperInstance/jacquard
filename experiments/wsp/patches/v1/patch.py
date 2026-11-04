#!/usr/bin/env python3
"""Data-driven weight-patch applier (Jacquard Phase 15, PATCH-PROTOCOL).

Usage:
  python3 patch.py --edits edits.json --model BASE_DIR --out OUT_DIR
                   [--exclude id,id,...] [--only id,id,...]

Loads the edits named in edits.json (minus --exclude, or only --only),
applies them to a copy of the base model directory, and prints a receipt:
edits applied, exact scalar count changed, fraction of total parameters.

Implementation notes:
- Pure stdlib + numpy (works under system python3 and the ML venv alike).
- safetensors files are patched in place inside the copied directory:
  the file is copied byte-for-byte and only the edited tensors' data
  segments are rewritten (same dtype/shape, so offsets never move).
  Every other tensor stays byte-identical to the base model.
- All arithmetic is done in float32 and rounded to bf16 with
  round-to-nearest-even, matching torch's bf16 add/scale semantics.
- No randomness anywhere; every new value is explicit in edits.json.
"""
import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

import numpy as np

TOTAL_PARAMS_FALLBACK = None  # computed from safetensors headers


# ---------- bf16 helpers ----------
def bf16_to_f32(u16):
    return (u16.astype(np.uint32) << 16).view(np.float32)


def f32_to_bf16(x):
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    rounded = (u + np.uint32(0x7FFF) + ((u >> np.uint32(16)) & np.uint32(1))) >> np.uint32(16)
    return rounded.astype(np.uint16)


# ---------- safetensors ----------
def read_header(path):
    with open(path, "rb") as f:
        (hlen,) = struct.unpack("<Q", f.read(8))
        header = json.loads(f.read(hlen))
    return 8 + hlen, header


def tensor_total_params(header):
    total = 0
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        n = 1
        for d in meta["shape"]:
            n *= d
        total += n
    return total


def apply_edits_to_shard(path, edits):
    """Apply edits targeting tensors in this shard. Returns (changed, total_params)."""
    data_start, header = read_header(path)
    total = tensor_total_params(header)
    targets = {}
    for e in edits:
        targets.setdefault(e["tensor"], []).append(e)
    changed = 0
    with open(path, "r+b") as f:
        for tname, tedits in targets.items():
            if tname not in header:
                continue
            meta = header[tname]
            if meta["dtype"] != "BF16":
                raise ValueError(f"{tname}: only BF16 tensors supported, got {meta['dtype']}")
            shape = meta["shape"]
            if len(shape) != 2:
                raise ValueError(f"{tname}: expected 2D tensor, got shape {shape}")
            rows_n, cols_n = shape
            start, end = meta["data_offsets"]
            f.seek(data_start + start)
            raw = f.read(end - start)
            orig = np.frombuffer(raw, dtype=np.uint16).reshape(rows_n, cols_n).copy()
            work = orig.copy()
            for e in tedits:
                sel = e["selector"]
                kind = sel["kind"]
                if kind == "rows":
                    idx = sel["rows"]
                    sub = work[idx, :]
                    if e["op"] == "add":
                        vals = np.asarray(e["value"], dtype=np.float64)
                        if vals.ndim == 1:
                            vals = np.tile(vals, (len(idx), 1))
                        new = f32_to_bf16(bf16_to_f32(sub) + vals.astype(np.float32))
                    elif e["op"] == "scale":
                        new = f32_to_bf16(bf16_to_f32(sub) * np.float32(e["value"]))
                    elif e["op"] == "set":
                        vals = np.asarray(e["value"], dtype=np.float64)
                        if vals.ndim == 1:
                            vals = np.tile(vals, (len(idx), 1))
                        new = f32_to_bf16(vals.astype(np.float32))
                    else:
                        raise ValueError(f"unknown op {e['op']}")
                    changed += int(np.count_nonzero(new != sub))
                    work[idx, :] = new
                elif kind == "elements":
                    coords = sel["coords"]  # list of [row, col]
                    vals = np.asarray(e["value"], dtype=np.float64).ravel()
                    assert len(coords) == len(vals)
                    for (r, c), v in zip(coords, vals):
                        old = work[r, c]
                        x = bf16_to_f32(np.array([old], dtype=np.uint16))[0]
                        if e["op"] == "add":
                            y = x + np.float32(v)
                        elif e["op"] == "scale":
                            y = x * np.float32(v)
                        elif e["op"] == "set":
                            y = np.float32(v)
                        else:
                            raise ValueError(f"unknown op {e['op']}")
                        newv = f32_to_bf16(np.array([y], dtype=np.float32))[0]
                        if newv != old:
                            changed += 1
                        work[r, c] = newv
                else:
                    raise ValueError(f"selector kind {kind!r} not supported by this applier")
            f.seek(data_start + start)
            f.write(work.astype(np.uint16).tobytes())
    return changed, total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edits", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", default="", help="comma-separated edit ids to skip")
    ap.add_argument("--only", default="", help="comma-separated edit ids to apply (only these)")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.edits).read_text(encoding="utf-8"))
    edits = doc["edits"] if isinstance(doc, dict) else doc
    exclude = {s for s in args.exclude.split(",") if s}
    only = {s for s in args.only.split(",") if s}
    known = {e["id"] for e in edits}
    unknown = (exclude | only) - known
    if unknown:
        raise SystemExit(f"unknown edit ids: {sorted(unknown)}")
    selected = [e for e in edits
                if (not only or e["id"] in only) and e["id"] not in exclude]

    model_dir, out_dir = Path(args.model), Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(model_dir, out_dir)

    total_changed, total_params = 0, 0
    for shard in sorted(out_dir.glob("*.safetensors")):
        c, t = apply_edits_to_shard(shard, selected)
        total_changed += c
        total_params += t
    if doc.get("total_parameters"):
        total_params = doc["total_parameters"]

    frac = total_changed / total_params if total_params else 0.0
    print(f"edits applied: {len(selected)} of {len(edits)} "
          f"({', '.join(e['id'] for e in selected) if selected else 'none'})")
    print(f"scalars changed: {total_changed}")
    print(f"total parameters: {total_params}")
    print(f"fraction changed: {frac:.6%}")
    print(f"sparsity bound (0.1%): {int(total_params * 0.001)} scalars "
          f"-> {'WITHIN BOUND' if total_changed <= total_params * 0.001 else 'OVER BOUND'}")
    print(f"model written to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
