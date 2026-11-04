#!/usr/bin/env python3
"""Apply (or roll back) the W3 hygiene head patch, surgically.

- head.weight [3,256] lives in the external data file at offset 55808,
  length 3072 bytes (float32, row-major, class rows neg/zero/pos).
  Patched by an in-place byte write of exactly those 3072 bytes.
- head.bias [3] lives inline in the .onnx protobuf; patched via the
  onnx package with load_external_data=False so every external-data
  reference (and the .data file layout) is preserved untouched.
Usage:
  apply_patch.py --src pristine_dir --dst out_dir --weights fit_results.json --candidate C_combined
  apply_patch.py --src patched_dir  --dst rollback_dir --weights head_pristine.json --rollback
Writes <dst>/edits.json enumerating every changed scalar (old, new)."""
import argparse, json, shutil, pathlib
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True)
ap.add_argument("--weights", required=True); ap.add_argument("--candidate", default=None)
ap.add_argument("--rollback", action="store_true")
a = ap.parse_args()
src, dst = pathlib.Path(a.src), pathlib.Path(a.dst)
if dst.exists(): shutil.rmtree(dst)
shutil.copytree(src, dst)
if a.rollback:
    hp = json.load(open(a.weights)); W1 = np.array(hp["W0"], dtype=np.float32); b1 = np.array(hp["b0"], dtype=np.float32)
    W0 = None  # read current (patched) values from dst for the edit record
else:
    fr = json.load(open(a.weights)); cand = fr["candidates"][a.candidate]
    W1 = np.array(cand["W"], dtype=np.float32); b1 = np.array(cand["b"], dtype=np.float32)
# --- weight: byte surgery on the .data file ---
import onnx, onnx.numpy_helper as nh
m = onnx.load(str(dst / "intuition_student.onnx"), load_external_data=False)
off = None
for t in m.graph.initializer:
    if t.name == "head.weight":
        off = int({e.key: e.value for e in t.external_data}["offset"])
assert off is not None
data_path = dst / "intuition_student.onnx.data"
buf = bytearray(open(data_path, "rb").read())
W_cur = np.frombuffer(bytes(buf[off:off+3072]), dtype=np.float32).reshape(3, 256).copy()
buf[off:off+3072] = W1.astype("<f4").tobytes()
open(data_path, "wb").write(bytes(buf))
# --- bias: onnx initializer surgery (external refs preserved) ---
for t in m.graph.initializer:
    if t.name == "head.bias":
        b_cur = nh.to_array(t).astype(np.float32).copy()
        t.CopyFrom(nh.from_array(b1, name="head.bias"))
onnx.save(m, str(dst / "intuition_student.onnx"))
edits = []
for i in range(3):
    for j in range(256):
        if float(W_cur[i, j]) != float(W1[i, j]):
            edits.append({"tensor": "head.weight", "index": [i, j], "old": float(W_cur[i, j]), "new": float(W1[i, j])})
for i in range(3):
    if float(b_cur[i]) != float(b1[i]):
        edits.append({"tensor": "head.bias", "index": [i], "old": float(b_cur[i]), "new": float(b1[i])})
json.dump({"n_edits": len(edits), "edits": edits}, open(dst / "edits.json", "w"), indent=1)
import hashlib
print(json.dumps({"dst": str(dst), "n_edits": len(edits),
                  "onnx_sha256": hashlib.sha256(open(dst / "intuition_student.onnx", "rb").read()).hexdigest(),
                  "data_sha256": hashlib.sha256(open(data_path, "rb").read()).hexdigest()}, indent=1))
