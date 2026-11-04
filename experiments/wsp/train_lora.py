#!/usr/bin/env python3
"""E3 gradient pole: LoRA fine-tune on the diagnostic split ONLY.

Information budget parity with the patcher: the same 80 diagnostic
items (prompt + gold). Config fixed in advance (PLAN.md slice 42):
peft r=16, alpha=32, dropout 0.0, target q/k/v/o/gate/up/down,
AdamW lr 1e-4, 3 epochs, batch 8, completion-only loss (prompt
tokens masked), bf16, seed 42. Reply format = the bare gold answer
(the task's stated contract: "Answer with just the number."),
chat-templated exactly as the scorer presents items.
Output: merged model directory (base weights + LoRA merged).

Usage: train_lora.py --base DIR --diag FILE --out DIR
"""
import argparse, json, pathlib, random
import torch
from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          Trainer, TrainingArguments)
from peft import LoraConfig, get_peft_model


class DiagDataset(Dataset):
    def __init__(self, items, tok, max_len=256):
        self.rows = []
        for it in items:
            msgs = [{"role": "user", "content": it["prompt"]}]
            prompt_ids = tok.apply_chat_template(
                msgs, add_generation_prompt=True, enable_thinking=False)
            ans = str(it["answer"])
            if isinstance(it["answer"], float) and it["answer"] == int(it["answer"]):
                ans = str(int(it["answer"]))
            ans_ids = tok(ans + "<|im_end|>", add_special_tokens=False)["input_ids"]
            ids = prompt_ids + ans_ids
            labels = [-100] * len(prompt_ids) + ans_ids[:]
            self.rows.append((ids[:max_len], labels[:max_len]))

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        ids, labels = self.rows[i]
        return {"input_ids": ids, "labels": labels,
                "attention_mask": [1] * len(ids)}


def collate(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    input_ids, labels, attn = [], [], []
    for b in batch:
        k = n - len(b["input_ids"])
        input_ids.append(b["input_ids"] + [pad_id] * k)
        labels.append(b["labels"] + [-100] * k)
        attn.append(b["attention_mask"] + [0] * k)
    return {"input_ids": torch.tensor(input_ids),
            "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(attn)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--diag", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    random.seed(42); torch.manual_seed(42)

    tok = AutoTokenizer.from_pretrained(a.base)
    items = [json.loads(l) for l in open(a.diag)]
    ds = DiagDataset(items, tok)
    model = AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.bfloat16)
    model.config.use_cache = False
    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
                     task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    args = TrainingArguments(
        output_dir=str(pathlib.Path(a.out) / "_trainer"),
        per_device_train_batch_size=8, num_train_epochs=3,
        learning_rate=1e-4, lr_scheduler_type="linear",
        logging_steps=5, save_strategy="no", report_to=[],
        bf16=True, seed=42, data_seed=42, remove_unused_columns=False)
    trainer = Trainer(model=model, args=args, train_dataset=ds,
                      data_collator=lambda b: collate(b, tok.pad_token_id or 151643))
    trainer.train()
    merged = model.merge_and_unload()
    merged.save_pretrained(a.out)
    tok.save_pretrained(a.out)
    n = sum(p.numel() for p in merged.parameters())
    print(f"merged model saved to {a.out} ({n} params)")


if __name__ == "__main__":
    main()
