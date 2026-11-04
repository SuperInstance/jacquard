#!/usr/bin/env python3
"""Dump top-200 ranked neurons for C1/C2 from a probe .pt (act signal).
Usage: probe_top200.py <probe.pt> <out.json>"""
import json, sys
import numpy as np
import torch
from scipy.stats import rankdata

src, out = sys.argv[1], sys.argv[2]
d = torch.load(src, weights_only=False)
lab = d["labels"]
cats = np.array(lab["category"]); corr = np.array(lab["correct"])
X = d["act"].numpy().astype(np.float64).reshape(len(cats), -1)
ranks = rankdata(X, method="average", axis=0)

def contrast(pos):
    n1, n0 = int(pos.sum()), int((~pos).sum())
    auc = (ranks[pos].sum(0) - n1 * (n1 + 1) / 2) / (n1 * n0)
    return auc

def dump(auc, k=200):
    order = np.argsort(-np.abs(auc - 0.5))[:k]
    return [{"layer": int(j) // 3072, "neuron": int(j) % 3072, "auc": round(float(auc[j]), 4)} for j in order]

res = {
    "C1_wrong_vs_correct": dump(contrast(~corr)),
    "C2_failingcats_vs_weeksdays": dump(contrast(np.isin(cats, ["days_between", "weekday_offset", "add_days_count", "month_span"]))),
}
json.dump(res, open(out, "w"), indent=1)
print("wrote", out, {k: (v[0], v[-1]) for k, v in res.items()})
