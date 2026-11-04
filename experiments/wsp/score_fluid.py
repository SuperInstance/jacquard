#!/usr/bin/env python3
"""E3 fluid pole scorer: score the BASE model with a frozen prompt
package (system + few-shot) prepended to every item.

Mirrors score.py's generation contract exactly (greedy, per-split
token caps, EOS union, left padding) and reuses its scorers
(extract_last_number / arith_correct / run_check / fact_match)
by importing it as a module — score.py must sit beside this file.
The only difference from score.py is the conversation: system
message + few-shot turns precede the item prompt.

Usage: score_fluid.py --model DIR --package prompt.json
       --split NAME --out JSON
Splits: validation, heldout, forget_instr, forget_fact.
"""
import argparse, importlib.util, json, pathlib
import torch

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wsp_score", HERE / "score.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
BATCH = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    pkg = json.loads(pathlib.Path(a.package).read_text())
    system = pkg.get("system", "")
    fewshot = pkg.get("fewshot", [])
    items = S.load_items(a.split)
    tok, model, device, eos_ids = S.load_model(a.model)
    max_new = S.MAX_NEW_TOKENS[a.split]

    def convo_text(item):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        for fs in fewshot:
            msgs.append({"role": "user", "content": fs["user"]})
            msgs.append({"role": "assistant", "content": fs["assistant"]})
        msgs.append({"role": "user", "content": item["prompt"]})
        return tok.apply_chat_template(msgs, tokenize=False,
                                       add_generation_prompt=True,
                                       enable_thinking=False)

    outputs = []
    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        texts = [convo_text(it) for it in batch]
        enc = tok(texts, return_tensors="pt", padding=True).to(device)
        eos_arg = None
        if eos_ids:
            eos_arg = eos_ids[0] if len(eos_ids) == 1 else list(eos_ids)
        with torch.no_grad():
            out = model.generate(
                **enc, max_new_tokens=max_new, do_sample=False,
                num_beams=1, pad_token_id=tok.pad_token_id,
                eos_token_id=eos_arg)
        gen = out[:, enc["input_ids"].shape[1]:]
        outputs.extend(tok.decode(r, skip_special_tokens=True) for r in gen)

    records, per_cat = [], {}
    for it, raw in zip(items, outputs):
        if a.split in S.ARITH_SPLITS:
            extracted = S.extract_last_number(raw)
            gold = it["answer"]
            correct = S.arith_correct(extracted, gold)
        elif a.split == "forget_instr":
            extracted, gold = None, it["check"]
            correct = S.run_check(it["check"], raw)
        elif a.split == "forget_fact":
            extracted, gold = None, it["answer"]
            correct = S.fact_match(raw, it["answer"], it.get("aliases"))
        else:
            raise ValueError(a.split)
        records.append({"id": it["id"], "category": it["category"],
                        "gold": gold, "raw_output": raw,
                        "extracted": extracted, "correct": correct})
        c = per_cat.setdefault(it["category"], [0, 0])
        c[1] += 1; c[0] += 1 if correct else 0
    n = len(records)
    result = {"n": n, "accuracy": sum(r["correct"] for r in records) / n,
              "per_category": {k: {"correct": v[0], "n": v[1],
                                   "accuracy": v[0] / v[1]}
                               for k, v in sorted(per_cat.items())},
              "items": records}
    pathlib.Path(a.out).write_text(json.dumps(
        {"model": a.model, "package": a.package,
         "splits": {a.split: result}}, indent=1))
    print(f"{a.split}: accuracy = {result['accuracy']}")


if __name__ == "__main__":
    main()
