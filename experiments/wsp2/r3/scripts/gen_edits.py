#!/usr/bin/env python3
"""Generate edits.json for an R3 trial from probe_stats.json (no hand-typed neurons).

Groups (all edits are down_proj column scalings — one edit per neuron,
1024 scalars each):
  S  suppress wrong-associated:  C1 top_act, auc >= thi  (act higher on wrong items)
  B  boost correct-associated:   C1 top_act, auc <= tlo  (act higher on correct items)
  F  suppress failing-cat:       C2 top_act, auc >= 0.999 (act higher on failing cats)
  W  boost weeks_days-associated: C2 top_act, auc <= 0.001
Usage: gen_edits.py --trial NAME --out edits.json [--S K:scale] [--B K:scale] ...
"""
import argparse, json

STATS = "/home/caseydigennaro/wsp-exp16/r3/results/probe_stats.json"

def pick(contrast, pred, k):
    tops = json.load(open(STATS))["contrasts"][contrast]["top_act"]
    sel = [t for t in tops if pred(t["auc"])][:k]
    return sel

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--S"); ap.add_argument("--B"); ap.add_argument("--F"); ap.add_argument("--W")
    ap.add_argument("--critical", default="", help="comma group letters flagged critical")
    a = ap.parse_args()
    crit = {x for x in a.critical.split(",") if x}
    groups = []
    if a.S:
        k, s = a.S.split(":"); groups.append(("S", "suppress-wrong-associated-C1", pick("C1_wrong_vs_correct", lambda x: x >= 0.94, int(k)), float(s)))
    if a.B:
        k, s = a.B.split(":"); groups.append(("B", "boost-correct-associated-C1", pick("C1_wrong_vs_correct", lambda x: x <= 0.06, int(k)), float(s)))
    if a.F:
        k, s = a.F.split(":"); groups.append(("F", "suppress-failingcat-associated-C2", pick("C2_failingcats_vs_weeksdays", lambda x: x >= 0.999, int(k)), float(s)))
    if a.W:
        k, s = a.W.split(":"); groups.append(("W", "boost-weeksdays-associated-C2", pick("C2_failingcats_vs_weeksdays", lambda x: x <= 0.001, int(k)), float(s)))
    edits, provenance = [], {}
    for letter, gname, sel, scale in groups:
        for t in sel:
            L, n = t["layer"], t["neuron"]
            edits.append({
                "id": f"{letter}-L{L}N{n}",
                "tensor": f"model.layers.{L}.mlp.down_proj.weight",
                "selector": {"kind": "cols", "cols": [n]},
                "op": "scale", "value": scale,
                "group": gname, "critical": letter in crit,
            })
        provenance[letter] = {"group": gname, "scale": scale, "neurons": sel}
    doc = {"patch": f"jacquard-phase16-r3-{a.trial}", "base_model": "Qwen/Qwen3-0.6B (bf16), pristine at ~/wsp-exp/models/Qwen3-0.6B",
           "total_parameters": 751632384, "provenance": provenance, "edits": edits}
    json.dump(doc, open(a.out, "w"), indent=1)
    print(f"{a.trial}: {len(edits)} edits, scalars <= {len(edits) * 1024} = {len(edits) * 1024 / 751632384 * 100:.4f}%")
    for letter, gname, sel, scale in groups:
        print(f"  {letter} x{scale}: {[(t['layer'], t['neuron'], t['auc']) for t in sel]}")

if __name__ == "__main__":
    main()
