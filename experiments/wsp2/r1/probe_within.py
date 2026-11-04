#!/usr/bin/env python3
"""P5 — within-family separation on canonicalised held-out.
P1's headline AUCs mix source families; the gpu-windows family is
the only canonicalised held-out family carrying non-ALLOW golds,
so the honest test is within-family: do the diagnostic u_hold /
u_deny directions separate gold non-ALLOW from gold ALLOW among
gpu-windows items alone?  Also DENY-only AUCs over all 53."""
import json
from pathlib import Path
import torch
HOME = Path.home(); WORK = HOME / "wsp-exp16/r1"
def unit(v): return v / v.norm()
def auc(pos, neg):
    pos = [float(x) for x in pos]; neg = [float(x) for x in neg]
    return sum((p > n) + (p == n) * 0.5 for p in pos for n in neg) / (len(pos) * len(neg))
d0 = torch.load(HOME / "wsp-exp/e8/round1/work/probe.pt"); H0 = d0["H"].double(); gold0 = list(d0["gold"])
m = H0.mean(0)
u_hold = unit(H0[[i for i, g in enumerate(gold0) if g == "HOLD"]].mean(0) - m)
u_deny = unit(H0[[i for i, g in enumerate(gold0) if g == "DENY"]].mean(0) - m)
d1 = torch.load(WORK / "probe_heldout_canonical.pt"); H1 = d1["H"].double(); ids1 = list(d1["ids"]); gold1 = list(d1["gold"])
held = {r["id"]: r for r in (json.loads(ln) for ln in open(WORK / "batteries/heldout_canonical.jsonl", encoding="utf-8") if ln.strip())}
gpu = [i for i, x in enumerate(ids1) if held[x]["source"] == "gpu-windows"]
ga = [i for i in gpu if gold1[i] == "ALLOW"]; gn = [i for i in gpu if gold1[i] != "ALLOW"]
deny = [i for i, g in enumerate(gold1) if g == "DENY"]; allow = [i for i, g in enumerate(gold1) if g == "ALLOW"]
out = {"within_gpu": {"n_allow": len(ga), "n_nonallow": len(gn),
        "AUC_nonallow_vs_allow_on_u_hold": auc(H1[gn] @ u_hold, H1[ga] @ u_hold),
        "AUC_nonallow_vs_allow_on_u_deny": auc(H1[gn] @ u_deny, H1[ga] @ u_deny)},
       "all_heldout": {"AUC_deny_vs_allow_on_u_hold": auc(H1[deny] @ u_hold, H1[allow] @ u_hold),
        "AUC_deny_vs_allow_on_u_deny": auc(H1[deny] @ u_deny, H1[allow] @ u_deny)}}
print(json.dumps(out, indent=1))
(WORK / "results/probe_within.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
