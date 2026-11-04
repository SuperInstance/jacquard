#!/usr/bin/env python3
"""Student scorer for the E7 signal-chain soft-joint battery.

Runs ON THE THOR against a model directory (Qwen3-0.6B chat format):

  ~/ml/.venv/bin/python score_joint.py --model DIR \
      --battery diagnostic.jsonl --out results_diag.json
  ~/ml/.venv/bin/python score_joint.py --model DIR \
      --battery heldout.jsonl --out results_held.json
  ~/ml/.venv/bin/python score_joint.py --selftest   # no model needed

Each battery item's message is wrapped in one fixed prompt:

  Classify the message as code, mixed, or model. Answer with just
  the label.

  <message>

Greedy decoding, max 8 new tokens. The predicted label is the FIRST
occurrence of code|mixed|model (case-insensitive, word-boundary) in
the raw output; no occurrence means the item is wrong with
extracted=None.

Output JSON mirrors the phase's score.py style:
  {"model": DIR, "splits": {<split>: {"n", "accuracy", "per_class",
  "confusion", "items": [{"id", "category", "gold", "raw_output",
  "extracted", "correct"}]}}}
where <split> is taken from the items' own split field, per_class is
keyed by gold label, and confusion maps gold -> predicted -> count
(unparseable outputs land under the key "none").

Model-loading conventions mirror score.py exactly: chat template with
enable_thinking=False (a tokenizer that rejects the flag is a loud
error, never a silent prompt change), EOS ids collected as the union
of generation_config.json and the tokenizer, bfloat16, left padding.
"""
import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTION = ("Classify the message as code, mixed, or model. "
               "Answer with just the label.")
MAX_NEW_TOKENS = 8
BATCH_SIZE = 16
LABELS = ("code", "mixed", "model")
_LABEL_RE = re.compile(r"\b(code|mixed|model)\b", re.IGNORECASE)


# ================= pure helpers (no torch) =================

def build_prompt(message):
    return f"{INSTRUCTION}\n\n{message}"


def extract_label(text):
    """First word-boundary occurrence of code|mixed|model,
    case-insensitive; None if there is none."""
    m = _LABEL_RE.search(text or "")
    return m.group(1).lower() if m else None


def summarise(records):
    """Accuracy + per-class + confusion from scored records."""
    per_class, confusion = {}, {}
    for r in records:
        gold, pred = r["gold"], r["extracted"]
        c = per_class.setdefault(gold, [0, 0])
        c[1] += 1
        c[0] += 1 if r["correct"] else 0
        row = confusion.setdefault(gold, {})
        key = pred if pred is not None else "none"
        row[key] = row.get(key, 0) + 1
    n = len(records)
    acc = sum(r["correct"] for r in records) / n if n else 0.0
    return {"n": n, "accuracy": acc,
            "per_class": {k: {"correct": v[0], "n": v[1],
                              "accuracy": v[0] / v[1]}
                          for k, v in sorted(per_class.items())},
            "confusion": {k: dict(sorted(v.items()))
                          for k, v in sorted(confusion.items())}}


def run_selftest():
    cases = []

    def case(name, got, want):
        cases.append((name, got, want))

    case("plain code", extract_label("code"), "code")
    case("capitalised", extract_label("Model"), "model")
    case("first wins", extract_label("mixed, not code"), "mixed")
    case("sentence", extract_label("The label is model."), "model")
    case("none present", extract_label("I am unsure"), None)
    case("empty", extract_label(""), None)
    case("no substring match", extract_label("encode the modem"),
         None)
    case("prompt fixed", build_prompt("X"),
         INSTRUCTION + "\n\nX")
    recs = [{"gold": "code", "extracted": "code", "correct": True},
            {"gold": "code", "extracted": None, "correct": False},
            {"gold": "model", "extracted": "mixed", "correct": False}]
    s = summarise(recs)
    case("selftest accuracy", round(s["accuracy"], 4), round(1 / 3, 4))
    case("selftest confusion none",
         s["confusion"]["code"].get("none"), 1)
    bad = 0
    for name, got, want in cases:
        ok = got == want
        bad += 0 if ok else 1
        print(f"{'ok' if ok else 'FAIL'}: {name} "
              f"(got {got!r}, want {want!r})")
    print(f"SELFTEST {'PASS' if not bad else 'FAIL'} ({len(cases)} cases)")
    return 1 if bad else 0


# ================= model-dependent scoring =================

def chat_text(tokenizer, prompt):
    msgs = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError as e:
        # Mirror score.py: fail loudly, never silently change the
        # prompt by dropping the thinking flag.
        raise TypeError(
            "tokenizer.apply_chat_template rejected "
            "enable_thinking=False; refusing to fall back to a "
            f"different prompt form: {e}") from e


def collect_eos_ids(model_dir, tok):
    """Union of eos ids from generation_config.json and tokenizer."""
    ids = set()

    def _add(v):
        if v is None:
            return
        if isinstance(v, (list, tuple)):
            for x in v:
                _add(x)
        else:
            ids.add(int(v))

    _add(getattr(tok, "eos_token_id", None))
    gc_path = Path(model_dir) / "generation_config.json"
    if gc_path.exists():
        try:
            gc = json.loads(gc_path.read_text(encoding="utf-8"))
            _add(gc.get("eos_token_id"))
        except Exception:  # noqa: BLE001
            pass
    return sorted(ids)


def load_model(model_dir):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, torch_dtype=torch.bfloat16)
    model.to(device)
    model.eval()
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    eos_ids = collect_eos_ids(model_dir, tok)
    return tok, model, device, eos_ids


def generate_batch(tok, model, device, prompts, eos_ids=None):
    import torch
    texts = [chat_text(tok, p) for p in prompts]
    enc = tok(texts, return_tensors="pt", padding=True).to(device)
    eos_arg = None
    if eos_ids:
        eos_arg = eos_ids[0] if len(eos_ids) == 1 else list(eos_ids)
    with torch.no_grad():
        out = model.generate(
            **enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
            num_beams=1, pad_token_id=tok.pad_token_id,
            eos_token_id=eos_arg)
    gen = out[:, enc["input_ids"].shape[1]:]
    return [tok.decode(row, skip_special_tokens=True) for row in gen]


def load_battery(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="model directory (on the Thor)")
    ap.add_argument("--battery", help="battery JSONL (either split)")
    ap.add_argument("--out", help="output JSON path")
    ap.add_argument("--selftest", action="store_true",
                    help="exercise pure helpers; no model needed")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.model or not args.battery:
        ap.error("--model and --battery are required (unless --selftest)")

    items = load_battery(args.battery)
    tok, model, device, eos_ids = load_model(args.model)
    prompts = [build_prompt(it["message"]) for it in items]
    outputs = []
    for i in range(0, len(prompts), BATCH_SIZE):
        outputs.extend(generate_batch(
            tok, model, device, prompts[i:i + BATCH_SIZE],
            eos_ids=eos_ids))
    records = []
    for it, raw in zip(items, outputs):
        pred = extract_label(raw)
        records.append({"id": it["id"], "category": it["subtype"],
                        "gold": it["label"], "raw_output": raw,
                        "extracted": pred,
                        "correct": pred == it["label"]})
    split = items[0]["split"] if items else "unknown"
    res = summarise(records)
    res["items"] = records
    print(f"{split}: accuracy={res['accuracy']:.4f} (n={res['n']})")
    for lab in LABELS:
        pc = res["per_class"].get(lab)
        if pc:
            print(f"  {lab}: {pc['correct']}/{pc['n']} "
                  f"({pc['accuracy']:.3f})")
    print(f"  confusion (gold -> predicted): "
          f"{json.dumps(res['confusion'])}")
    if args.out:
        Path(args.out).write_text(
            json.dumps({"model": args.model, "splits": {split: res}},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
