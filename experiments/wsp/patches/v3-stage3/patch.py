#!/usr/bin/env python3
"""Data-driven patch applier (Jacquard Phase 15 patch protocol).

Usage:
  python3 patch.py --edits edits.json --model BASE_DIR --out OUT_DIR
                   [--exclude id,id,...] [--only id,id,...]

Loads the base model weights, applies the edits named in edits.json
(minus --exclude, or only --only), writes a complete model directory to
OUT_DIR, and prints a receipt: edits applied, exact scalar count changed,
fraction of total parameters. No randomness; every new value is explicit
in edits.json.
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

    base = Path(args.model)
    out = Path(args.out)
    spec = json.loads(Path(args.edits).read_text())
    edits = spec["edits"]
    exclude = {x for x in args.exclude.split(",") if x}
    only = {x for x in args.only.split(",") if x}
    chosen = [e for e in edits
              if e["id"] not in exclude and (not only or e["id"] in only)]

    weights = load_file(str(base / "model.safetensors"))
    total_params = sum(math.prod(t.shape) for t in weights.values())

    changed = 0
    for e in chosen:
        t = weights[e["tensor"]]
        sel = e["selector"]
        assert sel["kind"] == "rows", sel
        row = sel["row"]
        old = t[row].float()
        val = torch.tensor(e["value"], dtype=torch.float32)
        if e["op"] == "add":
            new = old + val
        elif e["op"] == "set":
            new = val
        elif e["op"] == "scale":
            new = old * float(e["value"])
        else:
            raise ValueError(e["op"])
        new = new.to(t.dtype)
        changed += int((new != t[row]).sum().item())
        t[row] = new

    out.mkdir(parents=True, exist_ok=True)
    for f in base.iterdir():
        if f.name != "model.safetensors":
            shutil.copy2(f, out / f.name)
    save_file(weights, str(out / "model.safetensors"),
              metadata={"format": "pt"})
    frac = changed / total_params
    print(f"edits applied: {len(chosen)}")
    print(f"scalars changed: {changed}")
    print(f"total parameters: {total_params}")
    print(f"fraction changed: {frac * 100:.5f}% "
          f"(bound 0.1% = {int(total_params * 0.001)} scalars)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
