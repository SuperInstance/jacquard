#!/usr/bin/env python3
"""R3 secondary probe: MLP act MEAN-POOLED over all prompt tokens.
Same discipline as probe_extract.py (T2 diagnostic only, base model)."""
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "/home/caseydigennaro/wsp-exp/models/Qwen3-0.6B"
DIAG = "/home/caseydigennaro/wsp-exp16/r3/t2_diagnostic.jsonl"
BASE_RES = "/home/caseydigennaro/wsp-exp16/r3/results/base_t2_diagnostic.json"
OUT = "/home/caseydigennaro/wsp-exp16/r3/probe_mean.pt"

items = [json.loads(l) for l in open(DIAG) if l.strip()]
res = json.load(open(BASE_RES))["splits"]["t2_diagnostic"]["items"]
correct = {r["id"]: bool(r["correct"]) for r in res}
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda().eval()
layers = model.model.layers
gate_buf, up_buf = {}, {}
def mk(store, i):
    def hook(mod, inp, out): store[i] = out.detach()
    return hook
hs = []
for i, layer in enumerate(layers):
    hs.append(layer.mlp.gate_proj.register_forward_hook(mk(gate_buf, i)))
    hs.append(layer.mlp.up_proj.register_forward_hook(mk(up_buf, i)))
def chat_text(p):
    return tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
A = []
with torch.no_grad():
    for it in items:
        gate_buf.clear(); up_buf.clear()
        enc = tok(chat_text(it["prompt"]), return_tensors="pt").to("cuda")
        model(**enc)
        g = torch.stack([gate_buf[i][0].float() for i in range(len(layers))])  # [L, T, 3072]
        u = torch.stack([up_buf[i][0].float() for i in range(len(layers))])
        A.append((torch.nn.functional.silu(g) * u).mean(1).cpu())  # mean of per-token act
for h in hs: h.remove()
A = torch.stack(A)
labels = {"ids": [i["id"] for i in items], "category": [i["category"] for i in items],
          "correct": [correct[i["id"]] for i in items], "gold": [i["answer"] for i in items]}
torch.save({"act": A, "labels": labels}, OUT)
print("saved", OUT, tuple(A.shape))
