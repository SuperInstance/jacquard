#!/usr/bin/env python3
"""E8 round-1 authored weight patch for the decision student (Qwen3-0.6B).

Recomputes five unit directions from the BASE model final hidden states
over the diagnostic export, forms two row deltas, and writes them into
BOTH tied copies (model.embed_tokens.weight and lm_head.weight) of the
 HOLD (17542) and  DENY (66186) rows of a COPY of the student.
The  ALLOW / ALLOW rows are not edited: ALLOW is the default the
other two rows must beat.

Directions (all unit vectors in the 1024-d final-hidden space):
  mh     : mean hidden state over all 112 diagnostic prompts.
  u_hold : mean hidden of gold-HOLD items minus global mean.
  u_deny : mean hidden of gold-DENY items (n=3) minus global mean.
  u_rule : mean hidden of standing-rule-in-force ALLOW items (proof-run-2
           030-036, n=7) minus mean hidden of no-standing-rule gold-HOLD
           proof items (n=35).
  u_read : mean hidden of class agent-read ALLOW items (n=3) minus the
           same no-standing-rule gold-HOLD proof mean.

Full deltas:
  delta_HOLD = +0.50*u_hold - 0.45*u_rule - 0.30*u_read
  delta_DENY = +0.15*mh     + 0.50*u_deny

Variants:
  full           : as above.
  minus-critical : drops the CRITICAL components (u_hold; mh+u_deny),
                   leaving only the supporting suppressors on HOLD.
  minus-random   : drops a seeded-random pair of components
                   (random.Random(1234) shuffle of the 5 component
                   names, first two dropped), recorded in edits.json.

Usage: python3 patch.py --variant full --out DIR
"""
import argparse, json, random, shutil, sys
from pathlib import Path
import torch
from safetensors.torch import load_file, save_file

BASE = Path.home() / "wsp-exp/e8/work/student-base"
DIAG = Path.home() / "wsp-exp/e8/round1/diag_export.jsonl"
HOLD_ID, DENY_ID = 17542, 66186
TOTAL_SCALARS = 751_632_384
COMPONENTS = {  # name -> (row, coefficient, critical?)
    "u_hold_on_HOLD": ("HOLD", 0.50, True),
    "u_rule_on_HOLD": ("HOLD", -0.45, False),
    "u_read_on_HOLD": ("HOLD", -0.30, False),
    "mh_on_DENY": ("DENY", 0.15, True),
    "u_deny_on_DENY": ("DENY", 0.50, True),
}

def compute_hidden():
    sys.path.insert(0, str(Path.home() / "wsp-exp/e8"))
    from score_decision import build_prompt, chat_text
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(BASE))
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(str(BASE), torch_dtype=torch.bfloat16).cuda().eval()
    rows = [json.loads(l) for l in open(DIAG)]
    texts = [chat_text(tok, build_prompt(r["context"])) for r in rows]
    hs = []
    with torch.no_grad():
        for i in range(0, len(texts), 16):
            enc = tok(texts[i:i+16], return_tensors="pt", padding=True).to("cuda")
            out = model(**enc, output_hidden_states=True)
            hs.append(out.hidden_states[-1][:, -1, :].float().cpu())
    return torch.cat(hs), rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["full", "minus-critical", "minus-random"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hscale", type=float, default=1.0)
    ap.add_argument("--dscale", type=float, default=1.0)
    args = ap.parse_args()
    H, rows = compute_hidden()
    gold = [r["gold"] for r in rows]
    def mean_of(sel): return H[sel].mean(0)
    def unit(v): return v / v.norm()
    all_idx = list(range(len(rows)))
    hold_idx = [i for i, g in enumerate(gold) if g == "HOLD"]
    deny_idx = [i for i, g in enumerate(gold) if g == "DENY"]
    rule_yes = [i for i, r in enumerate(rows) if "standing rule in force for this shape: yes" in r["context"]]
    rule_no_hold = [i for i, r in enumerate(rows) if "proof" in r["source"] and "standing rule in force for this shape: none" in r["context"] and r["gold"] == "HOLD"]
    reads = [i for i, r in enumerate(rows) if "class: agent-read" in r["context"]]
    m = mean_of(all_idx)
    dirs = {
        "u_hold_on_HOLD": unit(mean_of(hold_idx) - m),
        "u_rule_on_HOLD": unit(mean_of(rule_yes) - mean_of(rule_no_hold)),
        "u_read_on_HOLD": unit(mean_of(reads) - mean_of(rule_no_hold)),
        "mh_on_DENY": unit(m),
        "u_deny_on_DENY": unit(mean_of(deny_idx) - m),
    }
    provenance = {
        "mh": {"definition": "mean hidden over all diagnostic items", "n": len(all_idx)},
        "u_hold": {"definition": "mean hidden gold-HOLD minus global mean", "n": len(hold_idx), "ids": [rows[i]["id"] for i in hold_idx]},
        "u_deny": {"definition": "mean hidden gold-DENY minus global mean", "n": len(deny_idx), "ids": [rows[i]["id"] for i in deny_idx]},
        "u_rule": {"definition": "mean hidden standing-rule-yes ALLOW minus mean hidden no-rule proof gold-HOLD", "n_yes": len(rule_yes), "n_no_hold": len(rule_no_hold), "yes_ids": [rows[i]["id"] for i in rule_yes]},
        "u_read": {"definition": "mean hidden agent-read ALLOW minus mean hidden no-rule proof gold-HOLD", "n": len(reads), "ids": [rows[i]["id"] for i in reads]},
    }
    dropped = []
    if args.variant == "minus-critical":
        dropped = [k for k, v in COMPONENTS.items() if v[2]]
    elif args.variant == "minus-random":
        names = sorted(COMPONENTS)
        random.Random(1234).shuffle(names)
        dropped = names[:2]
    deltas = {"HOLD": torch.zeros(1024), "DENY": torch.zeros(1024)}
    row_scale = {"HOLD": args.hscale, "DENY": args.dscale}
    used = []
    for name, (row, coef, crit) in COMPONENTS.items():
        if name in dropped: continue
        deltas[row] = deltas[row] + coef * row_scale[row] * dirs[name]
        used.append({"component": name, "row_token_id": HOLD_ID if row == "HOLD" else DENY_ID, "coefficient": coef, "critical": crit})
    sd = load_file(str(BASE / "model.safetensors"))
    changed = 0
    for tensor_name in ["model.embed_tokens.weight", "lm_head.weight"]:
        W = sd[tensor_name].float()
        for row_name, tid in [("HOLD", HOLD_ID), ("DENY", DENY_ID)]:
            new = (W[tid] + deltas[row_name]).to(torch.bfloat16)
            changed += int((new != sd[tensor_name][tid]).sum())
            W[tid] = new.float()
        sd[tensor_name] = W.to(torch.bfloat16)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    for fn in ["config.json", "generation_config.json", "merges.txt", "tokenizer_config.json", "tokenizer.json", "vocab.json"]:
        shutil.copy(BASE / fn, out / fn)
    save_file(sd, str(out / "model.safetensors"), metadata={"format": "pt"})
    edits = {
        "variant": args.variant, "base": str(BASE), "token_ids": {" HOLD": HOLD_ID, " DENY": DENY_ID},
        "rows_edited_per_tensor": 2, "tensors_edited": ["model.embed_tokens.weight", "lm_head.weight"],
        "logical_scalars_changed_max": 2 * 2 * 1024, "physical_scalars_differing_after_bf16": changed,
        "budget_scalars_0.1pct": int(0.001 * TOTAL_SCALARS), "total_scalars": TOTAL_SCALARS,
        "components_used": used, "components_dropped": dropped,
        "delta_norms": {k: float(v.norm()) for k, v in deltas.items()},
        "row_scales": row_scale,
        "direction_provenance": provenance,
    }
    (out / "edits.json").write_text(json.dumps(edits, indent=1))
    print(json.dumps({"variant": args.variant, "dropped": dropped, "changed_scalars": changed, "delta_norms": edits["delta_norms"]}, indent=1))

if __name__ == "__main__":
    main()
