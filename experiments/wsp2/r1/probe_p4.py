#!/usr/bin/env python3
"""P4 — E8's orthogonalised overlap direction, reconstructed.
E8 (EXPLANATION.md): 'an orthogonalised overlap direction
separates the 6 overlap items (proj ~21.3-21.5) from
no-contention board items (~15.3)' and on it the trio projects
21.33 vs legal overlaps 21.53 — identical.  Orthogonalisation
here: overlap mean-difference direction with its component
along the global mean direction mh removed, then unit-normalised
(the global mean dominates these hidden states, norm ~168, so
an un-orthogonalised direction mostly re-measures it).
Also: trio vs ordinary board on the same-seat direction
(E8: trio 45.11 vs ordinary board ALLOW 45.28)."""
import json, sys
from pathlib import Path
import torch
HOME = Path.home(); WORK = HOME / "wsp-exp16/r1"
sys.path.insert(0, str(WORK / "scripts"))
from probe_analyze import auc, unit, stats

def load(p): return [json.loads(ln) for ln in open(p, encoding="utf-8") if ln.strip()]
diag = {r["id"]: r for r in load(HOME / "wsp-exp/e8/batteries/diagnostic.jsonl")}
diag_x = {r["id"]: r for r in load(WORK / "batteries/diagnostic_crossformat.jsonl")}
held_c = {r["id"]: r for r in load(WORK / "batteries/heldout_canonical.jsonl")}

def orth_overlap(H, ids, meta):
    mh = unit(H.mean(0))
    board = [i for i, x in enumerate(ids) if meta[x]["source"] == "board-shadow"]
    over = [i for i in board if "contention: overlaps" in meta[ids[i]]["context"]]
    trio = [i for i in over if meta[ids[i]].get("operator_correct") is False]
    legal = [i for i in over if meta[ids[i]].get("operator_correct") is None]
    nocont = [i for i in board if i not in over]
    d = H[over].mean(0) - H[nocont].mean(0)
    d_orth = unit(d - (d @ mh) * mh)
    u_seat = unit(H[trio].mean(0) - H[legal].mean(0))
    return {
      "AUC_overlap_vs_nocont_on_u_over_orth": auc(H[over] @ d_orth, H[nocont] @ d_orth),
      "proj_overlap_on_u_over_orth": stats(H[over] @ d_orth),
      "proj_nocont_on_u_over_orth": stats(H[nocont] @ d_orth),
      "proj_trio_on_u_over_orth": stats(H[trio] @ d_orth),
      "proj_legal_on_u_over_orth": stats(H[legal] @ d_orth),
      "AUC_trio_vs_legal_on_u_over_orth": auc(H[trio] @ d_orth, H[legal] @ d_orth),
      "per_item_on_u_over_orth": {ids[i]: float(H[i] @ d_orth) for i in over},
      "proj_trio_on_u_seat": stats(H[trio] @ u_seat),
      "proj_nocont_board_on_u_seat": stats(H[nocont] @ u_seat),
      "proj_legal_on_u_seat": stats(H[legal] @ u_seat)}

out = {}
d0 = torch.load(HOME / "wsp-exp/e8/round1/work/probe.pt")
out["P4a_original_diagnostic"] = orth_overlap(d0["H"].double(), list(d0["ids"]), diag)
d2 = torch.load(WORK / "probe_diag_crossformat.pt")
out["P4b_crossformat_diagnostic"] = orth_overlap(d2["H"].double(), list(d2["ids"]), diag_x)
# extra P1 context: ALLOW stats on u_deny + gpu ALLOW projections
d = torch.load(HOME / "wsp-exp/e8/round1/work/probe.pt"); H0 = d["H"].double(); gold0 = list(d["gold"])
m = H0.mean(0); u_deny = unit(H0[[i for i,g in enumerate(gold0) if g=="DENY"]].mean(0) - m)
u_hold = unit(H0[[i for i,g in enumerate(gold0) if g=="HOLD"]].mean(0) - m)
d1 = torch.load(WORK / "probe_heldout_canonical.pt"); H1 = d1["H"].double(); ids1 = list(d1["ids"]); gold1 = list(d1["gold"])
allow = [i for i,g in enumerate(gold1) if g=="ALLOW"]
gpu_allow = [i for i in allow if held_c[ids1[i]]["source"]=="gpu-windows"]
out["P1_extra"] = {
  "proj_ALLOW_on_u_deny": stats(H1[allow] @ u_deny),
  "proj_gpu_ALLOW_on_u_hold": stats(H1[gpu_allow] @ u_hold),
  "proj_gpu_ALLOW_on_u_deny": stats(H1[gpu_allow] @ u_deny),
  "proj_all_ALLOW_on_u_hold": stats(H1[allow] @ u_hold)}
print(json.dumps(out, indent=1))
(WORK / "results/probe_p4.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
