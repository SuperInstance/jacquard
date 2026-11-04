#!/usr/bin/env python3
"""Extract head inputs (pooled vectors) + incumbent logits for core and
visible variant items, using the probe model. Preprocessing replicates
run_judge.py / server.py judge_one() exactly. NEVER reads the sealed file:
item paths are passed explicitly."""
import argparse, json
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--judge-dir", required=True)   # probe-model dir
ap.add_argument("--items", action="append", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
import onnxruntime as ort
from tokenizers import Tokenizer
tok = Tokenizer.from_file(f"{a.judge_dir}/tokenizer.json")
sess = ort.InferenceSession(f"{a.judge_dir}/intuition_student.onnx", providers=["CPUExecutionProvider"])
Q = "Should this action proceed?"
rows = []
for path in a.items:
    for line in open(path):
        if not line.strip(): continue
        r = json.loads(line)
        enc = tok.encode("[STATE] " + r["context"][:500] + " [QUESTION] " + Q)
        ids = enc.ids[:64] + [0]*max(0, 64-len(enc.ids))
        div, logits = sess.run(["div", "logits"], {"ids": np.array([ids], dtype=np.int64)})
        rows.append({"id": r["id"], "base_id": r.get("base_id", r["id"]),
                     "file": path.split("/")[-1], "kind": r.get("kind"), "class": r.get("class"),
                     "gold": r.get("gold"), "correct_outcome": r.get("correct_outcome"),
                     "operator_correct": r.get("operator_correct"),
                     "x": div[0].astype(np.float64).tolist(), "logits": logits[0].astype(np.float64).tolist(),
                     "n_tokens_full": len(enc.ids)})
np.savez_compressed(a.out, rows=np.array([json.dumps(r) for r in rows]))
print(f"wrote {a.out}: {len(rows)} rows")
