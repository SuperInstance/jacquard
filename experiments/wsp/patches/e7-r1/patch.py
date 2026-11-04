#!/usr/bin/env python3
"""E7 round-1 authored patch builder (canonical).

Reads edits.json (data-driven) + directions.npz (diagnostic-only geometry).
Each edit is applied to BOTH tied copies: model.embed_tokens.weight and
lm_head.weight (verified identical in the base file).
  components: direction  -> +scale * 2 * D_c           on the label row
              bias       -> +scale * bias_centered_c * m_hat
              calibration-> +gamma_c * m_hat  (measured offset cancellation,
                              gamma values are in edits.json)
Modes: --exclude ID... drops edits; --random-dir SEED replaces each D_c with
a random vector of identical norm (specificity control)."""
import argparse, json, shutil
from pathlib import Path
import numpy as np
BASE=Path("/home/caseydigennaro/wsp-exp/e7/work/student-base")
HERE=Path("/home/caseydigennaro/wsp-exp/e7/round1")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True)
    ap.add_argument("--exclude",nargs="*",default=[]); ap.add_argument("--random-dir",type=int,default=None)
    a=ap.parse_args()
    doc=json.loads((HERE/"edits.json").read_text()); scale=doc["scale"]
    dz=np.load(HERE/"directions.npz"); D=dz["D"].copy(); mhat=dz["mhat"]; bias=dz["bias_centered"]
    labs=["code","mixed","model"]; ids={"code":2038,"mixed":9519,"model":1614}
    if a.random_dir is not None:
        rng=np.random.default_rng(a.random_dir)
        D=np.stack([(lambda v: v/np.linalg.norm(v)*np.linalg.norm(D[i]))(rng.standard_normal(D.shape[1])) for i in range(3)])
    deltas={}
    for e in doc["edits"]:
        if e["id"] in a.exclude: continue
        i=labs.index(e["label"]); row=deltas.setdefault(ids[e["label"]], np.zeros(1024))
        if e["component"]=="direction": row += scale*2*D[i]
        elif e["component"]=="bias": row += scale*bias[i]*mhat
        elif e["component"]=="calibration": row += e["gamma"]*mhat
    from safetensors.torch import load_file, save_file
    import torch
    tensors=load_file(str(BASE/"model.safetensors")); changed=0
    for tid,delta in deltas.items():
        dt=torch.tensor(delta, dtype=torch.float32)
        for key in ("model.embed_tokens.weight","lm_head.weight"):
            tensors[key][tid]=(tensors[key][tid].float()+dt).to(tensors[key].dtype); changed+=1024
    out=Path(a.out)
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(BASE, out); save_file(tensors, str(out/"model.safetensors"), metadata={"format":"pt"})
    print(f"wrote {out} scale={scale} exclude={a.exclude} random_dir={a.random_dir} scalars_changed={changed}")
if __name__=="__main__": main()
