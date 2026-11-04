#!/usr/bin/env python3
"""Probe round 2: (a) cross-probe confusion matrices, (b) POOLED probe
(core + upper-visible + reorder-visible) with GroupKFold by base_id --
the honest test of whether ONE head can serve all conditions on unseen
bases, (c) incumbent prediction distributions per condition."""
import json, sys, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
rows = [json.loads(s) for s in np.load(sys.argv[1], allow_pickle=True)["rows"]]
CLS = ["DENY", "HOLD", "ALLOW"]; PRED = ["DENY", "HOLD", "ALLOW"]
def sel(f): return [r for r in rows if f(r)]
def XY(rs): return np.array([r["x"] for r in rs]), np.array([r["gold"] for r in rs])
def conf(y, p):
    return {g: {q: int(((y == g) & (p == q)).sum()) for q in CLS} for g in CLS}
core = sel(lambda r: r["file"] == "core.jsonl")
for kind in ("upper", "field_reorder"):
    var = sel(lambda r, k=kind: r["kind"] == k)
    cmap = {r["id"]: r for r in core}
    matched = [cmap[r["base_id"]] for r in var]
    Xm, ym = XY(matched); Xv, yv = XY(var)
    for nm, Xtr, ytr, Xte, yte in (("core->var", Xm, ym, Xv, yv), ("var->core", Xv, yv, Xm, ym)):
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, ytr)
        p = clf.predict(Xte)
        print(f"{kind} {nm}: acc={float((p==yte).mean()):.4f} pred_dist={collections.Counter(p.tolist())}")
        print("  conf:", json.dumps(conf(yte, p)))
    Lv = np.array([r["logits"] for r in var])
    print(f"{kind} incumbent pred_dist={collections.Counter([PRED[i] for i in Lv.argmax(1)]).most_common()}")
# pooled grouped CV
pool = core + sel(lambda r: r["kind"] in ("upper", "field_reorder"))
X, y = XY(pool); groups = np.array([r["base_id"] for r in pool])
conds = np.array([("core" if r["file"] == "core.jsonl" else r["kind"]) for r in pool])
gkf = GroupKFold(5)
pred = cross_val_predict(LogisticRegression(max_iter=2000, C=1.0), X, y, cv=gkf, groups=groups)
print(f"POOLED grouped-CV acc={float((pred==y).mean()):.4f} (majority {max(np.bincount([CLS.index(v) for v in y]))/len(y):.4f})")
for c in sorted(set(conds)):
    m = conds == c
    print(f"  cond {c}: acc={float((pred[m]==y[m]).mean()):.4f} conf={json.dumps(conf(y[m], pred[m]))}")
# pooled ungrouped CV for comparison (leaky across conditions, reported as such)
from sklearn.model_selection import StratifiedKFold
pred2 = cross_val_predict(LogisticRegression(max_iter=2000, C=1.0), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0))
print(f"POOLED ungrouped-CV acc={float((pred2==y).mean()):.4f} (base leakage across conditions possible)")
