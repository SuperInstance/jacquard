#!/usr/bin/env python3
"""Phase 16 R1 — hidden-state extraction for the representation
probes.  Adapted from Phase 15's ~/wsp-exp/e8/round1/work/probe.py:
same model (the unpatched base student), same scorer chat
rendering (score_decision.build_prompt / chat_text), final hidden
state at the last position, batch 16, bf16, CUDA.

Usage: probe_extract.py BATTERY.jsonl OUT.pt
OUT.pt: {"H", "L", "ids", "gold"} as in the Phase 15 probe.pt.
"""
import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_decision import build_prompt, chat_text  # noqa: E402

MODEL_DIR = str(Path.home() / "wsp-exp/e8/work/student-base")


def main():
    battery, out_path = sys.argv[1], sys.argv[2]
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, torch_dtype=torch.bfloat16).cuda().eval()
    rows = [json.loads(ln) for ln in
            open(battery, encoding="utf-8") if ln.strip()]
    texts = [chat_text(tok, build_prompt(r["context"])) for r in rows]
    hs, logits = [], []
    with torch.no_grad():
        for i in range(0, len(texts), 16):
            enc = tok(texts[i:i + 16], return_tensors="pt",
                      padding=True).to("cuda")
            out = model(**enc, output_hidden_states=True)
            hs.append(out.hidden_states[-1][:, -1, :].float().cpu())
            logits.append(out.logits[:, -1, :].float().cpu())
            print("batch", i, hs[-1].shape)
    H = torch.cat(hs)
    L = torch.cat(logits)
    torch.save({"H": H, "L": L,
                "ids": [r["id"] for r in rows],
                "gold": [r["gold"] for r in rows]}, out_path)
    print("saved", out_path, "H", tuple(H.shape),
          "mean norm %.2f" % H.norm(dim=1).mean().item())
    return 0


if __name__ == "__main__":
    sys.exit(main())
