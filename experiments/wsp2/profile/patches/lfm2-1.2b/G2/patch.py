#!/usr/bin/env python3
"""Canonical family-1 patch applier (PATCH-PROTOCOL shape).

  python3 patch.py --edits edits.json --model BASE --out OUT_DIR
                   [--exclude E1,E3] [--only E2] [--randomize-critical SEED]

BASE is a Hugging Face model directory or a single .gguf file (loaded
via the profile harness's GGUF route). Applies the row deltas recorded
in edits.json to every stored copy of the embedding / lm_head tensor,
writes a complete model directory to OUT_DIR, and prints a receipt
(edits applied, exact stored scalars changed, fraction of stored
parameters). Deterministic; the only randomness is the explicitly
seeded --randomize-critical ablation control.
"""
import argparse, json, shutil, sys
from pathlib import Path

EMB_KEYS = ("model.embed_tokens.weight", "lm_head.weight",
            "model.embed_tokens.weight".replace("model.", ""),
            "embed_tokens.weight", "token_embd.weight")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edits", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--randomize-critical", type=int, default=None)
    a = ap.parse_args()
    doc = json.loads(Path(a.edits).read_text())
    exclude = {x for x in a.exclude.split(",") if x}
    only = {x for x in a.only.split(",") if x}
    edits = [e for e in doc["edits"]
             if e["id"] not in exclude and (not only or e["id"] in only)]
    import numpy as np
    rng = np.random.default_rng(a.randomize_critical) if a.randomize_critical is not None else None
    deltas = {}
    for e in edits:
        v = np.array(e["value"], dtype=np.float64)
        if rng is not None and e["critical"]:
            r = rng.standard_normal(v.shape)
            v = r / np.linalg.norm(r) * np.linalg.norm(v)
        for row in e["selector"]["rows"]:
            deltas[row] = deltas.get(row, 0) + v
    base = Path(a.model); out = Path(a.out)
    changed = 0; total = 0
    if base.is_file() and base.suffix == ".gguf":
        sys.path.insert(0, str(Path.home() / "wsp-exp16/profile"))
        from run_profile import load_model
        import torch
        model, tok, _ = load_model(str(base))
        emb = model.get_input_embeddings().weight
        with torch.no_grad():
            for row, v in deltas.items():
                dt = torch.tensor(v, dtype=torch.float32).to(emb.device)
                emb.data[row] = (emb.data[row].float() + dt).to(emb.dtype)
                changed += emb.shape[1]
        total = sum(p.numel() for p in model.parameters())
        if out.exists(): shutil.rmtree(out)
        model.save_pretrained(str(out)); tok.save_pretrained(str(out))
    else:
        from safetensors.torch import load_file, save_file
        if out.exists(): shutil.rmtree(out)
        shutil.copytree(base, out)
        shards = sorted(out.glob("*.safetensors"))
        assert shards, "no safetensors in base dir"
        for shard in shards:
            tensors = load_file(str(shard))
            total += sum(t.numel() for t in tensors.values())
            hit = False
            for key in list(tensors):
                if key in EMB_KEYS:
                    import torch
                    W = tensors[key]
                    for row, v in deltas.items():
                        dt = torch.tensor(v, dtype=torch.float32)
                        W[row] = (W[row].float() + dt).to(W.dtype)
                        changed += W.shape[1]
                    hit = True
            if hit:
                save_file(tensors, str(shard), metadata={"format": "pt"})
    print(f"receipt: edits_applied={len(edits)} scalars_changed={changed} "
          f"stored_total={total} dose_percent={100.0*changed/total:.5f} "
          f"exclude={sorted(exclude)} only={sorted(only)} "
          f"randomize_critical={a.randomize_critical} out={out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
