#!/usr/bin/env python3
"""W3 judge runner — standalone copy of the jev-semantic judge.

Replicates EXACTLY the server-side preprocessing in ~/jev-rack/server.py
judge_one() (read-only source), which is INPUT-CONTRACT.md section 6:
  text[:500]; "[STATE] "+text+" [QUESTION] "+question; tokenizer.encode;
  ids[:64] right-padded with 0 to 64; int64 [1,64] input named "ids";
  softmax over logits (neg,zero,pos); verdict thresholds verbatim from
  server.py (settled -/+ / settled 0 / conflict / ignorance / lean).
Differences from server.py: none in preprocessing. Model/tokenizer are
loaded from a COPY directory (--judge-dir), never from ~/jev-rack/.
Question defaults to the trained go-no-go family question (see
build_core_and_variants.py header for the pre-stated mapping).
Prediction mapping: argmax pos->ALLOW, zero->HOLD, neg->DENY.
Usage: run_judge.py --judge-dir DIR --items core.jsonl [--items variants-visible.jsonl ...] --out results.json
"""
import argparse, json, sys
import numpy as np

QUESTION_DEFAULT = "Should this action proceed?"
VERDICT = None  # computed per server.py thresholds

def verdict_of(neg, zero, pos):
    return ("settled -" if neg > 0.6 else "settled +" if pos > 0.6 else
            "settled 0" if zero > 0.6 else "conflict" if neg > 0.3 and pos > 0.3 else
            "ignorance" if max(neg, zero, pos) < 0.5 else "lean")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--judge-dir", required=True)
    ap.add_argument("--items", action="append", required=True)
    ap.add_argument("--question", default=QUESTION_DEFAULT)
    ap.add_argument("--out", required=True)
    a=ap.parse_args()
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(f"{a.judge_dir}/tokenizer.json")
    sess=ort.InferenceSession(f"{a.judge_dir}/intuition_student.onnx", providers=["CPUExecutionProvider"])
    results=[]
    for path in a.items:
        for line in open(path):
            if not line.strip(): continue
            r=json.loads(line)
            text=r["context"]
            enc=tok.encode("[STATE] " + text[:500] + " [QUESTION] " + a.question)
            raw_ids=enc.ids
            ids=raw_ids[:64] + [0]*max(0, 64-len(raw_ids))
            logits=sess.run(None, {"ids": np.array([ids], dtype=np.int64)})[0][0]
            e=np.exp(logits-logits.max()); p=e/e.sum()
            neg,zero,pos=(round(float(x),4) for x in p)
            pred=("ALLOW" if pos>=zero and pos>=neg else "HOLD" if zero>=neg else "DENY")
            results.append({"id":r["id"],"base_id":r.get("base_id",r["id"]),
                "file":path.split("/")[-1],"class":r.get("class"),"kind":r.get("kind"),
                "split":r.get("split"),"source":r.get("source"),"gold":r.get("gold"),
                "operator_correct":r.get("operator_correct"),"correct_outcome":r.get("correct_outcome"),
                "neg":neg,"zero":zero,"pos":pos,"verdict":verdict_of(neg,zero,pos),"pred":pred,
                "n_tokens_full":len(raw_ids),"question_survives_64": ("[QUESTION]" in tok.decode(raw_ids[:64])) if len(raw_ids)>64 else True,
                "agree_operator": pred==r.get("gold"),
                "agree_correctness": (pred==r.get("correct_outcome")) if r.get("operator_correct") is not None else None})
    json.dump({"question":a.question,"n":len(results),"results":results}, open(a.out,"w"), indent=1)
    print(f"wrote {a.out}: {len(results)} rows")
if __name__=="__main__": sys.exit(main())
