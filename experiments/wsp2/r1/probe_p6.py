#!/usr/bin/env python3
"""P6 — E8's own orthogonalised contention direction (sim2.py
lines 11-22, replicated exactly), applied to BOTH the original
diagnostic export and the cross-format diagnostic battery.

sim2.py defines: u_cont_raw = unit(trio mean - no-contention
board ALLOW mean); uc = u_cont_raw orthogonalised against
[mh, u_hold, u_deny] in that order, renormalised.  E8's
EXPLANATION.md reports, on the original data, overlap items
projecting ~21.3-21.5 vs no-contention board ~15.3 on its
orthogonalised overlap direction and trio 21.33 vs legal
(null) overlaps 21.53; this replication checks those numbers
and then runs the identical computation on the cross-format
renderings."""
import json
from pathlib import Path
import torch
HOME = Path.home(); WORK = HOME / "wsp-exp16/r1"
def f(x): return float(x.item())
def auc(pos, neg):
    pos = [float(x) for x in pos]; neg = [float(x) for x in neg]
    return sum((p > n) + (p == n) * 0.5 for p in pos for n in neg) / (len(pos) * len(neg))
def run(H, rows, ids):
    gold = [r["gold"] for r in rows]
    labels = ["ALLOW", "HOLD", "DENY"]
    idx = {lab: [i for i, g in enumerate(gold) if g == lab] for lab in labels}
    m = H.mean(0); mh = m / m.norm()
    u_hold = (H[idx["HOLD"]].mean(0) - m); u_hold = u_hold / u_hold.norm()
    u_deny = (H[idx["DENY"]].mean(0) - m); u_deny = u_deny / u_deny.norm()
    board = [i for i, r in enumerate(rows) if r["source"] == "board-shadow"]
    trio = [i for i, r in enumerate(rows) if r.get("operator_correct") == False]
    none_board = [i for i in board if "contention: none" in rows[i]["context"] and rows[i].get("correct_outcome") == "ALLOW"]
    null_over = [i for i in board if "contention: overlaps" in rows[i]["context"] and rows[i].get("operator_correct") is None]
    over_all = [i for i in board if "contention: overlaps" in rows[i]["context"]]
    u_cont_raw = (H[trio].mean(0) - H[none_board].mean(0)); u_cont_raw = u_cont_raw / u_cont_raw.norm()
    uc = u_cont_raw.clone()
    for basis in [mh, u_hold, u_deny]:
        uc = uc - (uc @ basis) * basis
    resid = f(uc.norm()); uc = uc / uc.norm()
    def block(name, ii):
        p = H[ii] @ uc
        return {"n": len(ii), "mean": round(f(p.mean()), 2), "std": round(f(p.std()), 2),
                "min": round(f(p.min()), 2), "max": round(f(p.max()), 2)}
    return {"residual_norm_fraction": resid,
            "cos_cont_raw_with_mh_u_hold_u_deny": [round(f(u_cont_raw @ b), 4) for b in (mh, u_hold, u_deny)],
            "proj_on_uc": {"trio": block("trio", trio), "board_overlap_null": block("null", null_over),
                           "board_overlap_all": block("over", over_all), "board_none_allow": block("none", none_board),
                           "board_all": block("board", board)},
            "AUC_trio_vs_null_on_uc": auc(H[trio] @ uc, H[null_over] @ uc),
            "per_item_on_uc": {ids[i]: round(f(H[i] @ uc), 2) for i in over_all}}
out = {}
d0 = torch.load(HOME / "wsp-exp/e8/round1/work/probe.pt")
rows0 = [json.loads(ln) for ln in open(HOME / "wsp-exp/e8/round1/diag_export.jsonl", encoding="utf-8")]
out["P6a_original_diagnostic_sim2_replication"] = run(d0["H"], rows0, list(d0["ids"]))
d2 = torch.load(WORK / "probe_diag_crossformat.pt")
rows2 = [json.loads(ln) for ln in open(WORK / "batteries/diagnostic_crossformat.jsonl", encoding="utf-8")]
out["P6b_crossformat_diagnostic_sim2"] = run(d2["H"], rows2, list(d2["ids"]))
print(json.dumps(out, indent=1))
(WORK / "results/probe_p6.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
