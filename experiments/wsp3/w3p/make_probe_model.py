#!/usr/bin/env python3
"""Make a probe copy of the judge that also outputs the head input ('div',
the PAD-aware mean-pooled [1,256] vector feeding the final Gemm).
Weights untouched; only an extra graph output is declared.
Requires the `onnx` package (patcher's pylibs on the Thor)."""
import onnx, sys, pathlib
src, dst = sys.argv[1], sys.argv[2]
m = onnx.load(src, load_external_data=False)
vi = onnx.helper.make_tensor_value_info("div", onnx.TensorProto.FLOAT, [1, 256])
m.graph.output.append(vi)
pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
onnx.save(m, dst)
print("wrote", dst)
