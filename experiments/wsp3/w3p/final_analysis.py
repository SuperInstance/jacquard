#!/usr/bin/env python3
"""Final end-to-end accounting from run_judge.py outputs (pristine / patched /
rollback) plus a byte-level diff audit of the patched artefacts."""
import json, sys, hashlib
def load(p):
    d = json.load(open(p)); return {r["id"]: r for r in d["results"]}
pri, pat, rol = (load(f"work/results_{n}.json") for n in ("pristine", "patched", "rollback"))
def dual(rs):
    rs = list(rs)
    a = [r for r in rs if r["agree_operator"] is not None]
    b = [r for r in rs if r["agree_correctness"] is not None]
    per = {}
    for c in ("ALLOW", "HOLD", "DENY"):
        g = [r for r in rs if r["gold"] == c]
        per[c] = float(sum(r["pred"] == c for r in g) / len(g)) if g else None
    return {"n": len(rs), "agree_op": float(sum(r["agree_operator"] for r in a) / len(a)),
            "agree_correct": float(sum(r["agree_correctness"] for r in b) / len(b)), "n_correct": len(b),
            "per_class": per}
out = {}
for name, R in (("pristine", pri), ("patched", pat)):
    core = [r for r in R.values() if r["file"] == "core.jsonl"]
    e = {"core": dual(core)}
    for k in ("upper", "field_reorder", "trunc_half", "whitespace", "wrapper", "label_paraphrase"):
        e[k] = dual([r for r in R.values() if r.get("kind") == k])
    # retention: variant pred == same model's core pred for that base
    cmap = {r["base_id"]: r["pred"] for r in core}
    ret = {}
    for k in ("upper", "field_reorder", "trunc_half", "whitespace", "wrapper", "label_paraphrase"):
        vs = [r for r in R.values() if r.get("kind") == k]
        ret[k] = float(sum(r["pred"] == cmap[r["base_id"]] for r in vs) / len(vs))
    e["retention_vs_own_core"] = ret
    import collections
    e["core_pred_dist"] = dict(collections.Counter(r["pred"] for r in core))
    out[name] = e
# core moved accounting, patched vs pristine
moved = []
for cid, r0 in pri.items():
    if r0["file"] != "core.jsonl": continue
    r1 = pat[cid]
    if r1["pred"] != r0["pred"]:
        moved.append({"id": cid, "from": r0["pred"], "to": r1["pred"], "gold": r0["gold"],
                      "direction": "toward_gold" if r1["pred"] == r0["gold"] else
                                   ("away_from_gold" if r0["pred"] == r0["gold"] else "wrong_to_wrong")})
out["core_moved"] = {"n": len(moved),
                     "toward_gold": sum(1 for m in moved if m["direction"] == "toward_gold"),
                     "away_from_gold": [m for m in moved if m["direction"] == "away_from_gold"],
                     "wrong_to_wrong": [m for m in moved if m["direction"] == "wrong_to_wrong"]}
# rollback equality
diff = [i for i in pri if (pri[i]["neg"], pri[i]["zero"], pri[i]["pos"], pri[i]["pred"]) !=
        (rol[i]["neg"], rol[i]["zero"], rol[i]["pos"], rol[i]["pred"])]
out["rollback"] = {"rows_compared": len(pri), "rows_differing": len(diff)}
# byte audit
def data_bytes(p): return open(p, "rb").read()
b0, b1 = data_bytes("judge-pristine/intuition_student.onnx.data"), data_bytes("judge-patched/intuition_student.onnx.data")
idx = [i for i in range(len(b0)) if b0[i] != b1[i]]
out["byte_audit"] = {"data_len_equal": len(b0) == len(b1), "data_bytes_differing": len(idx),
                     "diff_range": [min(idx), max(idx)] if idx else None, "head_weight_range": [55808, 55808 + 3072],
                     "tokenizer_sha_equal": hashlib.sha256(open("judge-pristine/tokenizer.json", "rb").read()).hexdigest() ==
                                            hashlib.sha256(open("judge-patched/tokenizer.json", "rb").read()).hexdigest()}
print(json.dumps(out, indent=1))
json.dump(out, open("work/final_analysis.json", "w"), indent=1)
