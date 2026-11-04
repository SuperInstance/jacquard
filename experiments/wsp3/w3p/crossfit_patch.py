#!/usr/bin/env python3
"""Patch-procedure cross-fitting: GroupKFold by base_id over the pooled
diagnostic set (core + all visible variants). For each fold, fit the
combined-candidate objective on the other folds' bases and score the
held-out bases in every condition. Estimates the DELIVERED patch
procedure's generalisation to unseen bases (visible data only)."""
import json, sys
import numpy as np
from scipy.optimize import minimize
from sklearn.model_selection import GroupKFold
rows = [json.loads(s) for s in np.load(sys.argv[1], allow_pickle=True)["rows"]]
hp = json.load(open(sys.argv[2])); W0 = np.array(hp["W0"]); b0 = np.array(hp["b0"])
CI = {c: i for i, c in enumerate(["DENY", "HOLD", "ALLOW"])}
def fit(X, y, lam):
    n, d = X.shape; cnt = np.bincount(y, minlength=3); w = n/(3.0*np.maximum(cnt,1)); sw = w[y]
    def fg(v):
        W = v[:3*d].reshape(3, d); b = v[3*d:]
        Z = X @ W.T + b; Z -= Z.max(1, keepdims=True); E = np.exp(Z); P = E/E.sum(1, keepdims=True)
        ce = -float(np.sum(sw*np.log(np.maximum(P[np.arange(n), y], 1e-12)))/sw.sum())
        reg = lam*(float(((W-W0)**2).sum()) + float(((b-b0)**2).sum()))
        G = P.copy(); G[np.arange(n), y] -= 1; G *= (sw/sw.sum())[:, None]
        return ce+reg, np.concatenate([(G.T@X + 2*lam*(W-W0)).ravel(), G.sum(0) + 2*lam*(b-b0)])
    out = minimize(fg, np.concatenate([W0.ravel(), b0]), jac=True, method="L-BFGS-B", options={"maxiter": 600})
    return out.x[:3*256].reshape(3, 256), out.x[3*256:]
X = np.array([r["x"] for r in rows]); y = np.array([CI[r["gold"]] for r in rows])
groups = np.array([r["base_id"] for r in rows])
conds = np.array([("core" if r["file"] == "core.jsonl" else r["kind"]) for r in rows])
for lam in (0.01, 0.03, 0.1, 0.3):
    pred = np.zeros_like(y)
    for tr, te in GroupKFold(5).split(X, y, groups):
        W, b = fit(X[tr], y[tr], lam); pred[te] = (X[te] @ W.T + b).argmax(1)
    line = {"lam": lam, "pooled": float((pred == y).mean())}
    for c in ("core", "upper", "field_reorder", "whitespace", "wrapper", "trunc_half", "label_paraphrase"):
        m = conds == c; line[c] = float((pred[m] == y[m]).mean())
    print(json.dumps(line))
