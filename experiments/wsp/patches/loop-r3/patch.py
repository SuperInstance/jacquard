#!/usr/bin/env python3
"""Data-driven weight-patch applier — Jacquard Phase 15, E6 loop round 1.

Usage:
  python3 patch.py --model-in BASE_DIR --model-out OUT_DIR
                   [--edits edits.json]
                   [--exclude id,id,...]
                   [--exclude-critical] [--exclude-noncritical]
                   [--exclude-random-count N --random-seed S]
                   [--only id,id,...]

Every edit is declared in edits.json as a record
  {"id", "tensor", "index" (row), "selector", "op", "value",
   "group", "critical"}
No weight values live in this code: `add` takes its 1024-vector or scalar
from the record, `scale` takes its factor from the record. The applier
copies the model directory byte-for-byte and rewrites only the edited
tensors' data segments inside the copied safetensors shard (same
dtype/shape, so offsets never move); every other tensor stays
byte-identical to the input model. Arithmetic is float32 rounded to
bf16 (round-to-nearest-even), matching torch bf16 add/scale semantics.

Prints a receipt: records applied, exact scalars changed (bf16 words
whose value differs from the input), total parameters, % changed, and
the 0.1% sparsity-bound check.
"""
import argparse
import json
import random
import shutil
import struct
import sys
from pathlib import Path

import numpy as np


def bf16_to_f32(u16):
    return (u16.astype(np.uint32) << 16).view(np.float32)


def f32_to_bf16(x):
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    rounded = (u + np.uint32(0x7FFF) + ((u >> np.uint32(16)) & np.uint32(1))) >> np.uint32(16)
    return rounded.astype(np.uint16)


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
    data_start, header = read_header(path)
    total = tensor_total_params(header)
    targets = {}
    for e in edits:
        targets.setdefault(e["tensor"], []).append(e)
    changed = 0
    touched = 0
    with open(path, "r+b") as f:
        for tname, tedits in targets.items():
            if tname not in header:
                raise SystemExit(f"tensor {tname} not in shard {path}")
            meta = header[tname]
            if meta["dtype"] != "BF16":
                raise ValueError(f"{tname}: only BF16 supported, got {meta['dtype']}")
            shape = meta["shape"]
            if len(shape) != 2:
                raise ValueError(f"{tname}: expected 2D tensor, got {shape}")
            rows_n, cols_n = shape
            start, end = meta["data_offsets"]
            f.seek(data_start + start)
            raw = f.read(end - start)
            work = np.frombuffer(raw, dtype=np.uint16).reshape(rows_n, cols_n).copy()
            for e in tedits:
                rows = e["selector"]["rows"] if "selector" in e else [e["index"]]
                assert all(r == e["index"] for r in rows), "index/selector mismatch"
                for r in rows:
                    sub = work[r, :]
                    if e["op"] == "add":
                        vals = np.asarray(e["value"], dtype=np.float32)
                        if vals.ndim == 0:
                            vals = np.full(cols_n, float(vals), dtype=np.float32)
                        new = f32_to_bf16(bf16_to_f32(sub) + vals)
                    elif e["op"] == "scale":
                        new = f32_to_bf16(bf16_to_f32(sub) * np.float32(e["value"]))
                    elif e["op"] == "set":
                        vals = np.asarray(e["value"], dtype=np.float32)
                        if vals.ndim == 0:
                            vals = np.full(cols_n, float(vals), dtype=np.float32)
                        new = f32_to_bf16(vals)
                    else:
                        raise ValueError(f"unknown op {e['op']}")
                    touched += cols_n
                    changed += int(np.count_nonzero(new != sub))
                    work[r, :] = new
            f.seek(data_start + start)
            f.write(work.astype(np.uint16).tobytes())
    return changed, touched, total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-in", "--model", dest="model_in", required=True)
    ap.add_argument("--model-out", "--out", dest="model_out", required=True)
    ap.add_argument("--edits", default=str(Path(__file__).resolve().parent / "edits.json"))
    ap.add_argument("--exclude", default="", help="comma-separated edit ids to skip")
    ap.add_argument("--exclude-critical", action="store_true",
                    help="skip every edit whose record is marked critical (ablation)")
    ap.add_argument("--exclude-noncritical", action="store_true",
                    help="skip every edit whose record is marked non-critical (ablation)")
    ap.add_argument("--exclude-random-count", type=int, default=0,
                    help="skip N edit records chosen uniformly at random (ablation)")
    ap.add_argument("--random-seed", type=int, default=20261103)
    ap.add_argument("--only", default="", help="comma-separated edit ids to apply (only these)")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.edits).read_text(encoding="utf-8"))
    edits = doc["edits"] if isinstance(doc, dict) else doc
    known = {e["id"] for e in edits}
    exclude = {s for s in args.exclude.split(",") if s}
    only = {s for s in args.only.split(",") if s}
    unknown = (exclude | only) - known
    if unknown:
        raise SystemExit(f"unknown edit ids: {sorted(unknown)}")
    if args.exclude_critical:
        exclude |= {e["id"] for e in edits if e.get("critical")}
    if args.exclude_noncritical:
        exclude |= {e["id"] for e in edits if not e.get("critical")}
    random_excluded = []
    if args.exclude_random_count:
        rng = random.Random(args.random_seed)
        pool = [e["id"] for e in edits if e["id"] not in exclude and (not only or e["id"] in only)]
        random_excluded = rng.sample(pool, min(args.exclude_random_count, len(pool)))
        exclude |= set(random_excluded)
    selected = [e for e in edits
                if (not only or e["id"] in only) and e["id"] not in exclude]

    model_dir, out_dir = Path(args.model_in), Path(args.model_out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(model_dir, out_dir)

    total_changed, total_touched, total_params = 0, 0, 0
    for shard in sorted(out_dir.glob("*.safetensors")):
        c, t, tot = apply_edits_to_shard(shard, selected)
        total_changed += c
        total_touched += t
        total_params += tot
    if isinstance(doc, dict) and doc.get("total_parameters"):
        total_params = doc["total_parameters"]

    frac = total_changed / total_params if total_params else 0.0
    bound = int(total_params * 0.001)
    receipt = {
        "model_in": str(model_dir), "model_out": str(out_dir),
        "records_applied": len(selected), "records_total": len(edits),
        "records_applied_ids": [e["id"] for e in selected],
        "records_excluded_ids": sorted(exclude & known),
        "random_excluded_ids": random_excluded,
        "scalars_changed": total_changed, "scalars_touched": total_touched,
        "total_parameters": total_params, "fraction_changed": frac,
        "sparsity_bound_scalars": bound, "within_bound": total_changed <= bound,
    }
    print(f"records applied: {len(selected)} of {len(edits)} "
          f"({', '.join(receipt['records_applied_ids']) if selected else 'none'})")
    if random_excluded:
        print(f"randomly excluded ({len(random_excluded)}): {', '.join(random_excluded)}")
    print(f"scalars changed: {total_changed} (touched: {total_touched})")
    print(f"total parameters: {total_params}")
    print(f"fraction changed: {frac:.6%}")
    print(f"sparsity bound (0.1%): {bound} scalars -> "
          f"{'WITHIN BOUND' if receipt['within_bound'] else 'OVER BOUND'}")
    print(f"model written to: {out_dir}")
    (out_dir / "patch_receipt.json").write_text(json.dumps(receipt, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
