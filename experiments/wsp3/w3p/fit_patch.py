#!/usr/bin/env python3
"""Fit head-patch candidates on extracted head inputs (diagnostic data ONLY:
core 165 + variants-visible 510; the sealed file is never read).

Method (Phase-15-style measured directions, head-only): multinomial softmax
regression on the pooled head inputs, initialised at the incumbent head and
penalised by lambda*||W-W0||^2 + lambda*||b-b0||^2 (L2 pull toward the
incumbent), balanced class weights. Solved with L-BFGS (scipy).
Row order = ONNX class order (neg, zero, pos) = (DENY, HOLD, ALLOW).

Candidates: A = core+upper, B = core+field_reorder, C = core+all visible.
Selection rule (stated before fitting): among lambda values whose CORE
operator-agreement stays within 2 pts of baseline (56.36%) and whose core
ALLOW recall >= 75%, maximise the candidate's target-kind visible agreement
(for C: mean of upper and field_reorder visible agreement)."""
import json, sys
import numpy as np
from scipy.optimize import minimize
rows = [json.loads(s) for s in np.load(sys.argv[1], allow_pickle=True)["rows"]]
W0 = np.array(json.load(open(sys.argv[2]))["W0"]); b0 = np.array(json.load(open(sys.argv[2]))["b0"])
CLS = ["DENY", "HOLD", "ALLOW"]; CI = {c: i for i, c in enumerate(["DENY", "HOLD", "ALLOW"])}
PRED = ["DENY", "HOLD", "ALLOW"]
def XY(rs):
    X = np.array([r["x"] for r in rs]); y = np.array([CI[r["gold"]] for r in rs]); return X, y
def pred_of(X, W, b): return (X @ W.T + b).argmax(1)
def ev(rs, W, b):
    X, y = XY(rs); p = pred_of(X, W, b)
    per = {c: (float((p[y == CI[c]] == CI[c]).mean()) if (y == CI[c]).sum() else None) for c in CLS}
    co = [r.get("correct_outcome") for r in rs]
    m = np.array([c is not None for c in co])
    agc = float((np.array([PRED[i] for i in p])[m] == np.array(co)[m]).mean()) if m.sum() else None
    return {"n": len(rs), "agree_op": float((p == y).mean()), "agree_correct": agc, "per_class": per}
core = [r for r in rows if r["file"] == "core.jsonl"]
vis = [r for r in rows if r["file"] != "core.jsonl"]
by_kind = {k: [r for r in vis if r["kind"] == k] for k in sorted(set(r["kind"] for r in vis))}
core_pred0 = {r["id"]: PRED[i] for r, i in zip(core, pred_of(*XY(core)[0:1], W0, b0))} if False else None
Xc, yc = XY(core); p0 = pred_of(Xc, W0, b0)
core_pred0 = {r["id"]: PRED[i] for r, i in zip(core, p0)}

def fit(train, lam):
    X, y = train
    n, d = X.shape
    cnt = np.bincount(y, minlength=3); w = n / (3.0 * np.maximum(cnt, 1)); sw = w[y]
    def fg(v):
        W = v[:3*d].reshape(3, d); b = v[3*d:]
        Z = X @ W.T + b; Z -= Z.max(1, keepdims=True)
        E = np.exp(Z); P = E / E.sum(1, keepdims=True)
        ce = -float(np.sum(sw * np.log(np.maximum(P[np.arange(n), y], 1e-12))) / sw.sum())
        reg = lam * (float(((W-W0)**2).sum()) + float(((b-b0)**2).sum()))
        G = P.copy(); G[np.arange(n), y] -= 1; G *= (sw / sw.sum())[:, None]
        gW = G.T @ X + 2*lam*(W-W0); gb = G.sum(0) + 2*lam*(b-b0)
        return ce + reg, np.concatenate([gW.ravel(), gb])
    v0 = np.concatenate([W0.ravel(), b0])
    out = minimize(fg, v0, jac=True, method="L-BFGS-B", options={"maxiter": 600})
    return out.x[:3*256].reshape(3, 256), out.x[3*256:], out

def full_eval(W, b, label):
    e = {"label": label, "core": ev(core, W, b)}
    for k, rs in by_kind.items(): e[k] = ev(rs, W, b)
    X, y = XY(core); p = pred_of(X, W, b)
    moved = []
    for r, pi, yi in zip(core, p, y):
        if PRED[pi] != core_pred0[r["id"]]:
            moved.append({"id": r["id"], "from": core_pred0[r["id"]], "to": PRED[pi], "gold": r["gold"],
                          "direction": "toward_gold" if PRED[pi] == r["gold"] else
                                       ("away_from_gold" if core_pred0[r["id"]] == r["gold"] else "wrong_to_wrong")})
    e["core_moved"] = {"n": len(moved), "toward_gold": sum(1 for m in moved if m["direction"] == "toward_gold"),
                       "away_from_gold": sum(1 for m in moved if m["direction"] == "away_from_gold"),
                       "wrong_to_wrong": sum(1 for m in moved if m["direction"] == "wrong_to_wrong"),
                       "items": moved}
    print(json.dumps({k: v for k, v in e.items() if k != "core_moved"}, indent=1))
    print("core_moved:", {k: v for k, v in e["core_moved"].items() if k != "items"})
    return e

print("BASELINE (incumbent head, from extracted inputs)")
base = full_eval(W0, b0, "incumbent")
cands = {}
for name, train_rs, target in (("A_upper", core + by_kind["upper"], "upper"),
                               ("B_reorder", core + by_kind["field_reorder"], "field_reorder"),
                               ("C_combined", core + vis, None)):
    Xtr, ytr = XY(train_rs)
    print(f"\n##### candidate {name}: train n={len(train_rs)} #####")
    best = None
    for lam in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0):
        W, b, out = fit((Xtr, ytr), lam)
        ec = ev(core, W, b)
        tgt = (ev(by_kind[target], W, b)["agree_op"] if target else
               0.5*(ev(by_kind["upper"], W, b)["agree_op"] + ev(by_kind["field_reorder"], W, b)["agree_op"]))
        ok = ec["agree_op"] >= 0.5636 - 0.02 and (ec["per_class"]["ALLOW"] or 0) >= 0.75
        print(f"lam={lam}: core={ec['agree_op']:.4f} ALLOWrec={ec['per_class']['ALLOW']:.3f} "
              f"HOLDrec={ec['per_class']['HOLD']} target_score={tgt:.4f} ok={ok} |dW|={np.linalg.norm(W-W0):.3f}")
        if ok and (best is None or tgt > best[0]): best = (tgt, lam, W, b)
    if best:
        tgt, lam, W, b = best
        print(f"--> selected {name} lam={lam}")
        e = full_eval(W, b, name)
        cands[name] = {"lam": lam, "W": W.tolist(), "b": b.tolist(), "eval": e}
    else:
        print(f"--> {name}: NO lambda satisfied the retention rule")
json.dump({"baseline": base, "candidates": cands}, open(sys.argv[3], "w"), indent=1)
print("wrote", sys.argv[3])
