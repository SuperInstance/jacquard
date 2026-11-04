#!/usr/bin/env python3
"""R4 round-1 authored patch builder (family 1, PATCH-PROTOCOL shape).

Data-driven applier: reads edits.json + directions.npz (diagnostic-only
geometry) from the directory containing this script's edits file.
Each edit applies to BOTH tied copies (model.embed_tokens.weight and
lm_head.weight, verified byte-identical in the base file):
  direction   -> + coeff * D_c            on the label first-token row
  bias        -> + coeff * m_hat          (coeff = scale * bias_centered_c)
  calibration -> + gamma * m_hat
Modes: --exclude id,... drops edits; --only id,... keeps only those;
--random-dir SEED replaces each D_c with a random vector of identical
norm (specificity control for the E4 ablation). No other randomness.
"""
import argparse, json, shutil
from pathlib import Path
import numpy as np

LABELS = ["calm", "alarmed", "stampede"]
FIRST_TOK = {"calm": 19300, "alarmed": 81040, "stampede": 21206}
TOTAL_PARAMS = 751_632_384
HIDDEN = 1024

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edits", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--random-dir", type=int, default=None)
    a = ap.parse_args()
    edits_path = Path(a.edits)
    doc = json.loads(edits_path.read_text())
    dz = np.load(edits_path.parent / doc["directions_file"])
    D, mhat = dz["D"].copy(), dz["mhat"]
    if a.random_dir is not None:
        rng = np.random.default_rng(a.random_dir)
        D = np.stack([(lambda v: v / np.linalg.norm(v) * np.linalg.norm(D[i]))(rng.standard_normal(D.shape[1])) for i in range(3)])
    exclude = {x for x in a.exclude.split(",") if x}
    only = {x for x in a.only.split(",") if x}
    deltas = {}
    applied = []
    for e in doc["edits"]:
        if e["id"] in exclude or (only and e["id"] not in only):
            continue
        applied.append(e["id"])
        i = LABELS.index(e["label"])
        row = deltas.setdefault(FIRST_TOK[e["label"]], np.zeros(HIDDEN))
        if e["component"] == "direction":
            row += e["coeff"] * D[i]
        elif e["component"] in ("bias", "calibration"):
            row += e["coeff"] * mhat
        else:
            raise ValueError(e["component"])
    from safetensors.torch import load_file, save_file
    import torch
    base = Path(a.model)
    tensors = load_file(str(base / "model.safetensors"))
    changed = 0
    for tid, delta in deltas.items():
        dt = torch.tensor(delta, dtype=torch.float32)
        for key in ("model.embed_tokens.weight", "lm_head.weight"):
            tensors[key][tid] = (tensors[key][tid].float() + dt).to(tensors[key].dtype)
            changed += HIDDEN
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(base, out)
    save_file(tensors, str(out / "model.safetensors"), metadata={"format": "pt"})
    print(f"wrote {out} edits_applied={applied} scalars_changed={changed} "
          f"fraction={changed / TOTAL_PARAMS:.6%} of {TOTAL_PARAMS}")

if __name__ == "__main__":
    main()
