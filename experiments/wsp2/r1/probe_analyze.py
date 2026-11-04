#!/usr/bin/env python3
"""Phase 16 R1 — representation probes on the canonicalised data,
adapted from Phase 15's analyze.py (E8 round-1 work/analyze.py).

Directions are built ONLY from the ORIGINAL diagnostic export
(Phase 15 probe.pt, base model), exactly as E8 did, then applied
to the canonicalised sets:

  P0 validation: HOLD-vs-ALLOW projection AUC on the original
     diagnostic set must reproduce E8's 0.971.
  P1 canonicalised held-out (base-model hidden states of the
     canonical renderings): projections of gold ALLOW (n=47) vs
     gold non-ALLOW (n=6: 5 DENY + 1 HOLD) on the diagnostic
     u_hold (HOLD mean - global mean) and u_deny directions;
     AUC + per-item margins for the 6 non-ALLOW items.
  P2 cross-format diagnostic: the same-seat contention crux.
     Within board items (now in kernel form): the overlap
     direction (mean of the 6 'contention: overlaps' items minus
     mean of no-contention board items, unit) — AUC overlap vs
     no-contention; and the same-seat direction (trio mean minus
     legal/null-overlap mean, unit) — projections of the crux
     trio (operator_correct False, correct HOLD) vs the 3 legal
     overlaps (operator_correct None) vs ordinary board ALLOW;
     AUC trio vs legal overlaps.
  P3 the same P2 measurements on the ORIGINAL diagnostic board
     items (Phase 15 probe.pt), same code, for era comparison.

All AUCs are Mann-Whitney (ties 0.5), as in analyze.py.
Prints JSON to stdout.
"""
import json
import sys
from pathlib import Path

import torch

HOME = Path.home()
WORK = HOME / "wsp-exp16/r1"


def auc(pos, neg):
    pos = [float(x) for x in pos]
    neg = [float(x) for x in neg]
    return sum((p > n) + (p == n) * 0.5
               for p in pos for n in neg) / (len(pos) * len(neg))


def unit(v):
    return v / v.norm()


def stats(v):
    v = torch.as_tensor(v, dtype=torch.float64)
    return {"mean": float(v.mean()), "std": float(v.std()),
            "min": float(v.min()), "max": float(v.max())}


def main():
    out = {}
    d0 = torch.load(HOME / "wsp-exp/e8/round1/work/probe.pt")
    H0, gold0, ids0 = d0["H"].double(), list(d0["gold"]), list(d0["ids"])
    labels = ["ALLOW", "HOLD", "DENY"]
    idx = {lab: [i for i, g in enumerate(gold0) if g == lab]
           for lab in labels}
    m = H0.mean(0)
    u_hold = unit(H0[idx["HOLD"]].mean(0) - m)
    u_deny = unit(H0[idx["DENY"]].mean(0) - m)
    u_ha = unit(H0[idx["HOLD"]].mean(0) - H0[idx["ALLOW"]].mean(0))

    # ---- P0 validation on original diagnostic
    out["P0_original_diagnostic"] = {
        "hold_vs_allow_AUC_on_u_ha": auc(H0[idx["HOLD"]] @ u_ha,
                                         H0[idx["ALLOW"]] @ u_ha),
        "proj_ALLOW_on_u_ha": stats(H0[idx["ALLOW"]] @ u_ha),
        "proj_HOLD_on_u_ha": stats(H0[idx["HOLD"]] @ u_ha)}

    # ---- load batteries for item metadata
    def load(p):
        return [json.loads(ln) for ln in
                open(p, encoding="utf-8") if ln.strip()]
    diag = {r["id"]: r for r in load(
        HOME / "wsp-exp/e8/batteries/diagnostic.jsonl")}
    held_c = {r["id"]: r for r in load(
        WORK / "batteries/heldout_canonical.jsonl")}
    diag_x = {r["id"]: r for r in load(
        WORK / "batteries/diagnostic_crossformat.jsonl")}

    # ---- P1 canonicalised held-out
    d1 = torch.load(WORK / "probe_heldout_canonical.pt")
    H1, gold1, ids1 = d1["H"].double(), list(d1["gold"]), list(d1["ids"])
    assert ids1 == list(held_c.keys()), "heldout probe order mismatch"
    allow_i = [i for i, g in enumerate(gold1) if g == "ALLOW"]
    nonallow_i = [i for i, g in enumerate(gold1) if g != "ALLOW"]
    p1 = {"n_allow": len(allow_i), "n_nonallow": len(nonallow_i),
          "AUC_nonallow_vs_allow_on_u_hold":
              auc(H1[nonallow_i] @ u_hold, H1[allow_i] @ u_hold),
          "AUC_nonallow_vs_allow_on_u_deny":
              auc(H1[nonallow_i] @ u_deny, H1[allow_i] @ u_deny),
          "proj_ALLOW_on_u_hold": stats(H1[allow_i] @ u_hold),
          "proj_nonallow_items": []}
    for i in nonallow_i:
        p1["proj_nonallow_items"].append({
            "id": ids1[i], "gold": gold1[i],
            "source": held_c[ids1[i]]["source"],
            "proj_u_hold": float(H1[i] @ u_hold),
            "proj_u_deny": float(H1[i] @ u_deny),
            "margin_u_hold_vs_ALLOW_mean":
                float(H1[i] @ u_hold
                      - (H1[allow_i] @ u_hold).mean()),
            "margin_u_deny_vs_ALLOW_mean":
                float(H1[i] @ u_deny
                      - (H1[allow_i] @ u_deny).mean())})
    out["P1_canonical_heldout"] = p1

    # ---- contention probe (shared code for P2/P3)
    def contention(H, ids, meta):
        board = [i for i, id_ in enumerate(ids)
                 if meta[id_]["source"] == "board-shadow"]
        over = [i for i in board
                if "contention: overlaps" in meta[ids[i]]["context"]
                or "; contention: overlaps" in meta[ids[i]]["context"]]
        # cross-format board items carry contention inside requests;
        # the substring check above covers both renderings
        trio = [i for i in over
                if meta[ids[i]].get("operator_correct") is False]
        legal = [i for i in over
                 if meta[ids[i]].get("operator_correct") is None]
        nocont = [i for i in board if i not in over]
        u_over = unit(H[over].mean(0) - H[nocont].mean(0))
        u_seat = unit(H[trio].mean(0) - H[legal].mean(0))
        return {
            "n_board": len(board), "n_overlap": len(over),
            "n_trio": len(trio), "n_legal_overlap": len(legal),
            "trio_ids": [ids[i] for i in trio],
            "legal_ids": [ids[i] for i in legal],
            "AUC_overlap_vs_nocontention_on_u_over":
                auc(H[over] @ u_over, H[nocont] @ u_over),
            "proj_overlap_on_u_over": stats(H[over] @ u_over),
            "proj_nocontention_on_u_over": stats(H[nocont] @ u_over),
            "AUC_trio_vs_legal_on_u_seat":
                auc(H[trio] @ u_seat, H[legal] @ u_seat),
            "proj_trio_on_u_seat": stats(H[trio] @ u_seat),
            "proj_legal_on_u_seat": stats(H[legal] @ u_seat),
            "proj_trio_on_u_over": stats(H[trio] @ u_over),
            "proj_legal_on_u_over": stats(H[legal] @ u_over),
            "trio_minus_legal_margin_on_u_over":
                float((H[trio] @ u_over).mean()
                      - (H[legal] @ u_over).mean()),
            "per_item_on_u_over": {
                ids[i]: float(H[i] @ u_over) for i in over},
            "per_item_on_u_seat": {
                ids[i]: float(H[i] @ u_seat) for i in over}}

    d2 = torch.load(WORK / "probe_diag_crossformat.pt")
    out["P2_crossformat_diagnostic"] = contention(
        d2["H"].double(), list(d2["ids"]), diag_x)
    out["P3_original_diagnostic"] = contention(H0, ids0, diag)

    print(json.dumps(out, indent=1))
    (WORK / "results/probe_results.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ---- P4 appended analysis (run via probe_p4.py wrapper) ----
