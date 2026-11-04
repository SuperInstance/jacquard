#!/usr/bin/env python3
"""Reachability probes on extracted head inputs.
For each condition (core / upper-visible / field_reorder-visible):
 - multinomial logistic probe, 5-fold stratified CV accuracy (3-class gold)
 - binary ALLOW-vs-rest probe, 5-fold CV
 - LDA 5-fold CV
 - cross-condition: probe trained on matched core bases -> tested on variant (and reverse)
 - paired representation shift: cosine(x_core, x_variant) per base, ||x|| stats
 - class-mean geometry: cosine between gold-class means; Fisher ratio along
   the ALLOW-vs-rest mean-difference direction
Also: incumbent-head accuracy per condition (sanity, from extracted logits),
and a head-bias sweep on core (can a bias-only shift buy HOLD at <=2pt ALLOW cost?)."""
import json, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_predict

rows = [json.loads(s) for s in np.load(sys.argv[1], allow_pickle=True)["rows"]]
CLS = ["DENY", "HOLD", "ALLOW"]; IDX = {c: i for i, c in enumerate(["neg", "zero", "pos"])}
PRED = ["DENY", "HOLD", "ALLOW"]  # logits order neg,zero,pos -> DENY,HOLD,ALLOW

def get(cond):
    sel = [r for r in rows if cond(r)]
    X = np.array([r["x"] for r in sel]); y = np.array([r["gold"] for r in sel])
    L = np.array([r["logits"] for r in sel])
    return sel, X, y, L

def acc_cv(make, X, y, seed=0):
    if len(set(y)) < 3 or min(np.bincount([CLS.index(v) for v in y])) < 5:
        # fall back to binary-safe: still run if every class >=5 not met -> report via counts
        pass
    skf = StratifiedKFold(5, shuffle=True, random_state=seed)
    pred = cross_val_predict(make(), X, y, cv=skf)
    return float((pred == y).mean()), pred

def report(name, sel, X, y, L):
    pred_inc = np.array([PRED[i] for i in L.argmax(1)])
    out = {"n": len(y), "gold_counts": {c: int((y == c).sum()) for c in CLS},
           "incumbent_acc": float((pred_inc == y).mean())}
    p3, _ = acc_cv(lambda: LogisticRegression(max_iter=2000, C=1.0), X, y)
    out["logreg3_cv_acc"] = p3
    yb = (y == "ALLOW").astype(int)
    pb, _ = acc_cv(lambda: LogisticRegression(max_iter=2000, C=1.0), X, yb)
    out["logreg_allow_vs_rest_cv_acc"] = pb
    out["majority_baseline"] = float(max(np.bincount([CLS.index(v) for v in y])) / len(y))
    try:
        pl, _ = acc_cv(lambda: LinearDiscriminantAnalysis(), X, y)
        out["lda3_cv_acc"] = pl
    except Exception as e:
        out["lda3_cv_acc"] = f"ERR {e}"
    # class-mean geometry
    means = {c: X[y == c].mean(0) for c in CLS if (y == c).sum() >= 3}
    if len(means) == 3:
        def cos(u, v): return float(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)))
        out["classmean_cos"] = {f"{a}-{b}": cos(means[a], means[b]) for a, b in
                                [("ALLOW", "HOLD"), ("ALLOW", "DENY"), ("HOLD", "DENY")]}
        d = means["ALLOW"] - (means["HOLD"] + means["DENY"]) / 2
        proj = X @ d / (np.linalg.norm(d) ** 2)
        between = np.var([proj[y == c].mean() for c in CLS])
        within = np.mean([proj[y == c].var() for c in CLS])
        out["fisher_allow_vs_rest"] = float(between / within) if within > 0 else None
    out["x_norm_mean"] = float(np.linalg.norm(X, axis=1).mean())
    print(f"== {name} =="); print(json.dumps(out, indent=1))
    return out

core_sel, Xc, yc, Lc = get(lambda r: r["file"] == "core.jsonl")
res = {}
res["core_all165"] = report("core (all 165)", core_sel, Xc, yc, Lc)
for kind in ("upper", "field_reorder"):
    vsel, Xv, yv, Lv = get(lambda r, k=kind: r["kind"] == k)
    res[kind] = report(f"visible {kind} (n={len(vsel)})", vsel, Xv, yv, Lv)
    bases = [r["base_id"] for r in vsel]
    cmap = {r["id"]: r for r in core_sel}
    Xm = np.array([cmap[b]["x"] for b in bases]); ym = np.array([cmap[b]["gold"] for b in bases])
    res[f"core_matched_to_{kind}"] = report(f"core matched to {kind} bases", [cmap[b] for b in bases], Xm, ym,
                                            np.array([cmap[b]["logits"] for b in bases]))
    # paired shift
    cos = float(np.mean([float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))) for a, b in zip(Xm, Xv)]))
    print(f"paired cosine core->{kind}: {cos:.4f}  mean ||dx||={np.linalg.norm(Xm-Xv,axis=1).mean():.4f}")
    res.setdefault("paired_cosine", {})[kind] = cos
    # cross-condition probe transfer
    for tr_name, Xtr, ytr, te_name, Xte, yte in (("core", Xm, ym, kind, Xv, yv), (kind, Xv, yv, "core", Xm, ym)):
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, ytr)
        print(f"cross-probe train={tr_name} test={te_name}: acc={float((clf.predict(Xte)==yte).mean()):.4f}")
        res.setdefault("cross_probe", {})[f"{tr_name}->{te_name}"] = float((clf.predict(Xte) == yte).mean())

# bias sweep on core: add delta to zero-row (HOLD) bias, and neg-row (DENY) bias
print("== bias sweep on core (incumbent head) ==")
for row, lab in ((1, "HOLD bias"), (0, "DENY bias")):
    for d in (0.25, 0.5, 1.0, 2.0):
        L2 = Lc.copy(); L2[:, row] += d
        p = np.array([PRED[i] for i in L2.argmax(1)])
        per = {c: float((p[yc == c] == c).mean()) if (yc == c).sum() else None for c in CLS}
        print(f"{lab} +{d}: overall={float((p==yc).mean()):.4f} per-class={per} n_pred_HOLD={int((p=='HOLD').sum())} n_pred_DENY={int((p=='DENY').sum())}")
json.dump(res, open(sys.argv[2], "w"), indent=1)
print("wrote", sys.argv[2])
