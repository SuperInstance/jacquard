#!/usr/bin/env python3
"""E7 round-2 authored patch builder (data-driven, canonical).
Base = round-1 patched-r1 (inputs untouched). Reads edits.json config F +
directions_r2.npz. Delta_c = alpha*Wc_C3_c + (t*gamma_full_c + boost_c)*mhat
on BOTH tied copies (model.embed_tokens.weight, lm_head.weight).
Modes: --exclude ID... drops edits; --random-dir SEED replaces the Wc rows
with random same-norm vectors (specificity control)."""
import argparse, json, shutil
from pathlib import Path
import numpy as np
BASE=Path("/home/caseydigennaro/wsp-exp/e7/round1/patched-r1")
HERE=Path("/home/caseydigennaro/wsp-exp/e7/round2")
GAMMA=np.array([-0.0271138958632946, 0.014948646537959576, 0.0121652502566576])
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True)
    ap.add_argument("--exclude",nargs="*",default=[]); ap.add_argument("--random-dir",type=int,default=None)
    a=ap.parse_args()
    doc=json.loads((HERE/"edits.json").read_text()); cfg=doc["configs"]["F"]
    dz=np.load(HERE/"directions_r2.npz"); Wc=dz["Wc_C3"].copy(); mhat=dz["mhat"]
    labs=["code","mixed","model"]; ids={"code":2038,"mixed":9519,"model":1614}
    if a.random_dir is not None:
        rng=np.random.default_rng(a.random_dir)
        Wc=np.stack([(lambda v: v/np.linalg.norm(v)*np.linalg.norm(Wc[i]))(rng.standard_normal(Wc.shape[1])) for i in range(3)])
    deltas={}
    for e in doc["edits"]:
        if e["id"] in a.exclude: continue
        i=labs.index(e["label"]); row=deltas.setdefault(ids[e["label"]], np.zeros(1024))
        if e["component"]=="direction": row += cfg["alpha"]*Wc[i]
        elif e["component"]=="calibration": row += cfg["t"]*GAMMA[i]*mhat
        elif e["component"]=="boost": row += cfg["boost"][e["label"]]*mhat
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
    print(f"wrote {out} exclude={a.exclude} random_dir={a.random_dir} scalars_changed={changed}")
if __name__=="__main__": main()
