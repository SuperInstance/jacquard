#!/usr/bin/env python3
"""Generic edits generator from a rankings file (probe_top200.py output).
--spec "LETTER:contrast:hi|lo:K:scale,..."  hi -> auc>=0.90 side, lo -> auc<=0.10 side,
taken in ranked order, at most K. One down_proj col-scale edit per neuron.
--critical "S,B" flags groups critical."""
import argparse, json

ap = argparse.ArgumentParser()
ap.add_argument("--rankings", required=True)
ap.add_argument("--trial", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--spec", required=True)
ap.add_argument("--critical", default="")
a = ap.parse_args()
rank = json.load(open(a.rankings))
crit = {x for x in a.critical.split(",") if x}
edits, provenance = [], {}
for part in a.spec.split(","):
    letter, contrast, side, k, scale = part.split(":")
    lst = rank[contrast]
    sel = [t for t in lst if (t["auc"] >= 0.90 if side == "hi" else t["auc"] <= 0.10)][:int(k)]
    for t in sel:
        L, n = t["layer"], t["neuron"]
        edits.append({"id": f"{letter}-L{L}N{n}", "tensor": f"model.layers.{L}.mlp.down_proj.weight",
                      "selector": {"kind": "cols", "cols": [n]}, "op": "scale", "value": float(scale),
                      "group": f"{letter}-{contrast}-{side}", "critical": letter in crit})
    provenance[letter] = {"contrast": contrast, "side": side, "scale": float(scale), "neurons": sel}
    print(letter, len(sel), [(t["layer"], t["neuron"], t["auc"]) for t in sel[:6]], "...")
doc = {"patch": f"jacquard-phase16-r3-{a.trial}", "base_model": "Qwen/Qwen3-0.6B (bf16), pristine at ~/wsp-exp/models/Qwen3-0.6B",
       "total_parameters": 751632384, "rankings_file": a.rankings, "provenance": provenance, "edits": edits}
json.dump(doc, open(a.out, "w"), indent=1)
print(f"{a.trial}: {len(edits)} edits, scalars <= {len(edits) * 1024} = {len(edits) * 1024 / 751632384 * 100:.4f}%")
