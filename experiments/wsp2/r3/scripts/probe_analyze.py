#!/usr/bin/env python3
"""R3 probe analysis v2 — per-neuron discrimination, tie-correct AUC.

Changes from v1: AUC uses average ranks for ties (activations are
tie-heavy: exact zeros in sparse neurons; v1's unaveraged ranks let
file order — which is category-blocked — leak into the statistic).
All computations float64. Deterministic: fixed RNG seed, single run
writes results/probe_stats.json; verify by re-running and diffing.
"""
import json
import numpy as np
import torch

rng = np.random.default_rng(16046)
d = torch.load("/home/caseydigennaro/wsp-exp16/r3/probe_last.pt", weights_only=False)
lab = d["labels"]
cats = np.array(lab["category"]); corr = np.array(lab["correct"])
ids = lab["ids"]
prompts = {}
for l in open("/home/caseydigennaro/wsp-exp16/r3/t2_diagnostic.jsonl"):
    it = json.loads(l); prompts[it["id"]] = it["prompt"]
variant = np.array([
    "B_daysleft" if prompts[i].startswith("How many days are left")
    else ("A_landing" if c == "add_days_count" else "")
    for i, c in zip(ids, cats)])

def avg_ranks(X):
    """Average ranks (1..n) per column, ties averaged (scipy, C-speed)."""
    from scipy.stats import rankdata
    return rankdata(X, method="average", axis=0)

def auc_d(X, pos_mask, ranks=None):
    pos, neg = X[pos_mask], X[~pos_mask]
    n1, n0 = len(pos), len(neg)
    if ranks is None:
        ranks = avg_ranks(X)
    r1 = ranks[pos_mask].sum(0)
    auc = (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)
    m1, m0 = pos.mean(0), neg.mean(0)
    s1, s0 = pos.std(0, ddof=1), neg.std(0, ddof=1)
    sp = np.sqrt(((n1 - 1) * s1**2 + (n0 - 1) * s0**2) / max(n1 + n0 - 2, 1))
    dc = np.where(sp > 1e-12, (m1 - m0) / np.maximum(sp, 1e-12), 0.0)
    return auc, dc

def top_list(auc, dc, k=30):
    idx = np.argsort(-np.abs(auc - 0.5))[:k]
    return [{"layer": int(j) // 3072, "neuron": int(j) % 3072,
             "auc": round(float(auc[j]), 4), "cohen_d": round(float(dc[j]), 3)} for j in idx]

masks = {
    "C1_wrong_vs_correct": (np.ones(60, bool), ~corr),
    "C2_failingcats_vs_weeksdays": (
        np.isin(cats, ["days_between", "weekday_offset", "add_days_count", "month_span", "weeks_days"]),
        np.isin(cats, ["days_between", "weekday_offset", "add_days_count", "month_span"])),
    "C3_monthspan_vs_weeksdays": (
        np.isin(cats, ["month_span", "weeks_days"]), cats == "month_span"),
    "C4_daysleftB_vs_landingA": (variant != "", variant == "B_daysleft"),
}

report = {"n_neurons": 28 * 3072, "auc_method": "average-rank Mann-Whitney, float64", "contrasts": {}}
for cname, (subset, pos) in masks.items():
    entry = {"n_pos": int(pos[subset].sum()), "n_neg": int((~pos[subset]).sum())}
    for sig in ["act", "gate", "up"]:
        X = d[sig].numpy().astype(np.float64).reshape(60, -1)[subset]
        p = pos[subset]
        auc, dc = auc_d(X, p)
        entry[f"best_{sig}_auc"] = round(float(np.abs(auc - 0.5).max() + 0.5), 4)
        if sig == "act":
            entry["top_act"] = top_list(auc, dc)
            ranks = avg_ranks(X)
            n1 = int(p.sum()); n0 = len(p) - n1
            maxs = []
            for t in range(300):
                pp = rng.permutation(p)
                r1 = ranks[pp].sum(0)
                a2 = (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)
                maxs.append(float(np.abs(a2 - 0.5).max() + 0.5))
            entry["perm_max_auc_mean"] = round(float(np.mean(maxs)), 4)
            entry["perm_max_auc_p95"] = round(float(np.percentile(maxs, 95)), 4)
            entry["perm_max_auc_max"] = round(float(np.max(maxs)), 4)
    report["contrasts"][cname] = entry
    print(cname, json.dumps({k: v for k, v in entry.items() if k != "top_act"}), flush=True)

json.dump(report, open("/home/caseydigennaro/wsp-exp16/r3/results/probe_stats.json", "w"), indent=1)
print("wrote probe_stats.json")
