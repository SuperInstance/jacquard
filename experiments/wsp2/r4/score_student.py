#!/usr/bin/env python3
"""Student scorer for the R4 PanicDial battery (Thor).

Fresh Qwen3-0.6B base, zero-shot, greedy, one fixed prompt:

    Classify the room's alarm state as calm, alarmed, or
    stampede. Answer with just the label.

    Transcript:
    [+0s] <author>: <text>
    [+12s] <author>: <text> (reactions: 3, replies: 1)
    ...

The (reactions: N, replies: M) suffix appears only when the
message's total reaction heat or reply count is non-zero, so
the student receives every signal the incumbent reads (text,
relative timing, reaction heat, reply count) in text form.
Predicted label = first word-boundary occurrence of
calm|alarmed|stampede (case-insensitive) in the raw output;
none = wrong, extracted=None.

Model-loading conventions mirror experiments/wsp/e7/score_joint.py
and score.py: chat template with enable_thinking=False (a
tokenizer that rejects the flag is a loud error), EOS ids =
union of generation_config.json and the tokenizer, bfloat16,
left padding, batch 16, max 8 new tokens.
"""
import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTION = ("Classify the room's alarm state as calm, alarmed, or "
               "stampede. Answer with just the label.")
MAX_NEW_TOKENS = 8
BATCH_SIZE = 16
LABELS = ("calm", "alarmed", "stampede")
_LABEL_RE = re.compile(r"\b(calm|alarmed|stampede)\b", re.IGNORECASE)


def render_transcript(item):
    lines = []
    for m in item["messages"]:
        heat = sum(m["reactions"].values())
        suffix = ""
        if heat or m["n_replies"]:
            suffix = f" (reactions: {heat}, replies: {m['n_replies']})"
        lines.append(f"[+{m['ts']:.0f}s] {m['author']}: {m['text']}{suffix}")
    return "\n".join(lines)


def build_prompt(item):
    return f"{INSTRUCTION}\n\nTranscript:\n{render_transcript(item)}"


def extract_label(text):
    m = _LABEL_RE.search(text or "")
    return m.group(1).lower() if m else None


def summarise(records):
    per_class, confusion = {}, {}
    for r in records:
        c = per_class.setdefault(r["gold"], [0, 0])
        c[1] += 1
        c[0] += 1 if r["correct"] else 0
        row = confusion.setdefault(r["gold"], {})
        key = r["extracted"] if r["extracted"] is not None else "none"
        row[key] = row.get(key, 0) + 1
    n = len(records)
    return {"n": n,
            "accuracy": sum(r["correct"] for r in records) / n if n else 0.0,
            "per_class": {k: {"correct": v[0], "n": v[1],
                              "accuracy": v[0] / v[1]}
                          for k, v in sorted(per_class.items())},
            "confusion": {k: dict(sorted(v.items()))
                          for k, v in sorted(confusion.items())}}


def run_selftest():
    cases = []

    def case(name, got, want):
        cases.append((name, got, want))

    case("plain", extract_label("calm"), "calm")
    case("capitalised", extract_label("Alarmed"), "alarmed")
    case("first wins", extract_label("stampede, not calm"), "stampede")
    case("none", extract_label("I cannot tell"), None)
    case("no substring", extract_label("calmly does it"), None)
    item = {"messages": [
        {"author": "ana", "text": "hello", "ts": 0.0,
         "reactions": {}, "n_replies": 0},
        {"author": "bo", "text": "hi", "ts": 12.0,
         "reactions": {"signal": 3}, "n_replies": 1}]}
    case("render", render_transcript(item),
         "[+0s] ana: hello\n[+12s] bo: hi (reactions: 3, replies: 1)")
    case("prompt head", build_prompt(item).splitlines()[0], INSTRUCTION)
    bad = 0
    for name, got, want in cases:
        ok = got == want
        bad += 0 if ok else 1
        print(f"{'ok' if ok else 'FAIL'}: {name} (got {got!r}, want {want!r})")
    print(f"SELFTEST {'PASS' if not bad else 'FAIL'} ({len(cases)} cases)")
    return 1 if bad else 0


def chat_text(tokenizer, prompt):
    msgs = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError as e:
        raise TypeError(
            "tokenizer.apply_chat_template rejected enable_thinking=False; "
            f"refusing to fall back to a different prompt form: {e}") from e


def collect_eos_ids(model_dir, tok):
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
            _add(json.loads(gc_path.read_text(encoding="utf-8"))
                 .get("eos_token_id"))
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
    return tok, model, device, collect_eos_ids(model_dir, tok)


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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model")
    ap.add_argument("--battery")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.model or not args.battery:
        ap.error("--model and --battery are required (unless --selftest)")
    items = [json.loads(ln) for ln in
             Path(args.battery).read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    tok, model, device, eos_ids = load_model(args.model)
    prompts = [build_prompt(it) for it in items]
    outputs = []
    for i in range(0, len(prompts), BATCH_SIZE):
        outputs.extend(generate_batch(
            tok, model, device, prompts[i:i + BATCH_SIZE], eos_ids=eos_ids))
    records = []
    for it, raw in zip(items, outputs):
        pred = extract_label(raw)
        records.append({"id": it["id"], "category": it["subtype"],
                        "gold": it["label"], "raw_output": raw,
                        "extracted": pred, "correct": pred == it["label"]})
    split = items[0]["split"] if items else "unknown"
    res = summarise(records)
    res["items"] = records
    nb = [r for r in records if next(
        it["boundary"] for it in items if it["id"] == r["id"])]
    if nb:
        res["boundary_accuracy"] = sum(r["correct"] for r in nb) / len(nb)
    print(f"{split}: accuracy={res['accuracy']:.4f} (n={res['n']})")
    for lab in LABELS:
        pc = res["per_class"].get(lab)
        if pc:
            print(f"  {lab}: {pc['correct']}/{pc['n']} ({pc['accuracy']:.3f})")
    print(f"  confusion (gold -> predicted): {json.dumps(res['confusion'])}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(
            {"model": args.model, "prompt": INSTRUCTION,
             "splits": {split: res}}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
