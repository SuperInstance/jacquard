#!/usr/bin/env python3
"""Data-driven weight-patch applier — Jacquard Phase 16 R3 (family 2).

Usage:
  python3 patch.py --edits edits.json --model BASE_DIR --out OUT_DIR
                   [--exclude id,id,...] [--only id,id,...]

Applies the edits named in edits.json to a copy of the base model and
prints a receipt: edits applied, exact scalar count changed, fraction
of total parameters. Supported selectors on 2-D BF16 tensors:
  {"kind": "rows", "rows": [i, ...]}   -- tensor[i, :] for each i
  {"kind": "cols", "cols": [j, ...]}   -- tensor[:, j] for each j
Ops:
  "scale" -- value is a number; selected entries multiplied by it
             (deterministic formula over the base tensor's own values)
  "add"   -- value is a number (broadcast) or a list matching the
             selected slice length
  "set"   -- value is a number (broadcast) or a list as above
No randomness anywhere. Every edit is reversible by construction:
re-running from the pristine base with an edit excluded reproduces
the model without that edit exactly.
"""
import argparse, json, math, shutil, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edits", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    import torch
    from safetensors.torch import load_file, save_file

    base, out = Path(args.model), Path(args.out)
    spec = json.loads(Path(args.edits).read_text())
    edits = spec["edits"]
    exclude = {x for x in args.exclude.split(",") if x}
    only = {x for x in args.only.split(",") if x}
    known = {e["id"] for e in edits}
    unknown = (exclude | only) - known
    if unknown:
        raise SystemExit(f"unknown edit ids: {sorted(unknown)}")
    chosen = [e for e in edits if e["id"] not in exclude and (not only or e["id"] in only)]

    weights = load_file(str(base / "model.safetensors"))
    total_params = sum(math.prod(t.shape) for t in weights.values())

    changed = 0
    for e in chosen:
        t = weights[e["tensor"]]
        assert t.dim() == 2, (e["id"], t.shape)
        sel = e["selector"]
        if sel["kind"] == "rows":
            idx = sel["rows"]
            old = t[idx, :].float()
            sl = (idx, slice(None))
        elif sel["kind"] == "cols":
            idx = sel["cols"]
            old = t[:, idx].float()
            sl = (slice(None), idx)
        else:
            raise ValueError(f"selector kind {sel['kind']!r}")
        if e["op"] == "scale":
            new = old * float(e["value"])
        elif e["op"] in ("add", "set"):
            v = e["value"]
            val = torch.tensor(v, dtype=torch.float32) if isinstance(v, list) else torch.tensor(float(v))
            new = old + val if e["op"] == "add" else torch.broadcast_to(val, old.shape).clone() if val.dim() == 0 else val
        else:
            raise ValueError(e["op"])
        new = new.to(t.dtype)
        changed += int((new != t[sl]).sum().item())
        t[sl] = new

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in base.iterdir():
        if f.name != "model.safetensors":
            shutil.copy2(f, out / f.name)
    save_file(weights, str(out / "model.safetensors"), metadata={"format": "pt"})
    frac = changed / total_params
    print(f"edits applied: {len(chosen)} of {len(edits)} ({', '.join(e['id'] for e in chosen) if chosen else 'none'})")
    print(f"scalars changed: {changed}")
    print(f"total parameters: {total_params}")
    print(f"fraction changed: {frac * 100:.5f}% (bound 0.1% = {int(total_params * 0.001)} scalars) -> {'WITHIN BOUND' if changed <= total_params * 0.001 else 'OVER BOUND'}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
