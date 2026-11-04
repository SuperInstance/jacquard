#!/usr/bin/env python3
"""R3 probe extraction — Qwen3-0.6B MLP activations on T2 diagnostic ONLY.

For each diagnostic prompt (chat-templated exactly as score.py does),
run a single forward pass over the prompt and capture, at the LAST
prompt token position (the answer-initiation position), per layer:
  gate = gate_proj output, up = up_proj output, act = silu(gate)*up
Saves a .pt with tensors [n_items, 28, 3072] (float32) plus labels
taken from the diagnostic file and the base scoring result.
No generation, no other split is touched.
"""
import json, sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = "/home/caseydigennaro/wsp-exp/models/Qwen3-0.6B"
DIAG = "/home/caseydigennaro/wsp-exp16/r3/t2_diagnostic.jsonl"
BASE_RES = "/home/caseydigennaro/wsp-exp16/r3/results/base_t2_diagnostic.json"
OUT = "/home/caseydigennaro/wsp-exp16/r3/probe_last.pt"

items = [json.loads(l) for l in open(DIAG) if l.strip()]
res = json.load(open(BASE_RES))["splits"]["t2_diagnostic"]["items"]
correct = {r["id"]: bool(r["correct"]) for r in res}
assert [i["id"] for i in items] == [r["id"] for r in res]

tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16).cuda().eval()

layers = model.model.layers
gate_buf, up_buf = {}, {}

def mk_hook(idx, store):
    def hook(mod, inp, out):
        store[idx] = out.detach()
    return hook

handles = []
for i, layer in enumerate(layers):
    handles.append(layer.mlp.gate_proj.register_forward_hook(mk_hook(i, gate_buf)))
    handles.append(layer.mlp.up_proj.register_forward_hook(mk_hook(i, up_buf)))

def chat_text(prompt):
    msgs = [{"role": "user", "content": prompt}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)

G, U = [], []
with torch.no_grad():
    for it in items:
        gate_buf.clear(); up_buf.clear()
        text = chat_text(it["prompt"])
        enc = tok(text, return_tensors="pt").to("cuda")
        model(**enc)
        g = torch.stack([gate_buf[i][0, -1].float().cpu() for i in range(len(layers))])
        u = torch.stack([up_buf[i][0, -1].float().cpu() for i in range(len(layers))])
        G.append(g); U.append(u)
for h in handles: h.remove()

G = torch.stack(G); U = torch.stack(U)
A = torch.nn.functional.silu(G) * U
labels = {
    "ids": [i["id"] for i in items],
    "category": [i["category"] for i in items],
    "correct": [correct[i["id"]] for i in items],
    "gold": [i["answer"] for i in items],
}
torch.save({"gate": G, "up": U, "act": A, "labels": labels}, OUT)
print("saved", OUT, "gate", tuple(G.shape), "act mean|.|", float(A.abs().mean()))
print("correct:", sum(labels["correct"]), "/", len(items))
