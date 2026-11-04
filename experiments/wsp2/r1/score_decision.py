#!/usr/bin/env python3
"""Student scorer for the E8 decision battery (runs on the Thor).

Usage:
  python3 score_decision.py --model DIR --battery FILE --out results.json
  python3 score_decision.py --selftest

Mirrors the conventions of ../score.py: greedy decoding only, the
chat template applied with enable_thinking=False (a tokenizer
that rejects the flag fails loudly rather than silently changing
the prompt), the EOS union collected from generation_config.json
and the tokenizer, left padding, batch size 16.

Prompt (fixed, built from each item's `context` field):

  Governance decision.
  <context>
  Answer with just ALLOW, HOLD, or DENY.

Generation is capped at 8 new tokens. Extraction takes the first
outcome word in the reply (token-boundary, case-insensitive);
the synonyms queue/queued -> HOLD, denied/refused/rejected ->
DENY, allowed/approved -> ALLOW are accepted and the raw reply
is always recorded so any extraction can be audited.

Two accuracies per split, reported separately:
  (a) agreement-with-operator — gold is the item's recorded
      outcome (`gold`);
  (b) agreement-with-correctness — on the subset where
      `operator_correct` is known, gold is `correct_outcome`.
Output JSON: {"model": ..., "battery": ..., "splits":
{<split>: {"n", "accuracy_operator", "correctness": {"n",
"accuracy"}, "per_gold": {...}, "items": [...]}}} — the same
splits -> items style as ../score.py.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MAX_NEW_TOKENS = 8
BATCH_SIZE = 16
PROMPT_TEMPLATE = ("Governance decision.\n%s\n"
                   "Answer with just ALLOW, HOLD, or DENY.")
_TOKEN_MAP = {
    "allow": "ALLOW", "allowed": "ALLOW", "allows": "ALLOW",
    "approved": "ALLOW",
    "hold": "HOLD", "held": "HOLD",
    "queue": "HOLD", "queued": "HOLD",
    "deny": "DENY", "denied": "DENY", "denies": "DENY",
    "refused": "DENY", "rejected": "DENY",
}
_TOKEN_RE = re.compile(
    r"\b(allow|allowed|allows|approved|hold|held|queue|queued|"
    r"deny|denied|denies|refused|rejected)\b", re.IGNORECASE)


# ================= pure helpers (no torch) =================

def extract_outcome(text):
    """First outcome token in the reply, mapped to ALLOW/HOLD/
    DENY; None if there is none."""
    m = _TOKEN_RE.search(text or "")
    if not m:
        return None
    return _TOKEN_MAP[m.group(1).lower()]


def build_prompt(context):
    return PROMPT_TEMPLATE % context


def score_records(items, outputs):
    """Pure scoring core: zip battery items with raw outputs."""
    records = []
    for it, raw in zip(items, outputs):
        extracted = extract_outcome(raw)
        rec = {"id": it["id"], "gold": it["gold"],
               "operator_correct": it.get("operator_correct"),
               "correct_outcome": it.get("correct_outcome"),
               "raw_output": raw, "extracted": extracted,
               "correct_operator": extracted is not None
               and extracted == it["gold"],
               "correct_correctness": None}
        if it.get("operator_correct") is not None:
            rec["correct_correctness"] = extracted is not None \
                and extracted == it.get("correct_outcome")
        records.append(rec)
    n = len(records)
    acc_op = (sum(r["correct_operator"] for r in records) / n
              if n else 0.0)
    subset = [r for r in records
              if r["correct_correctness"] is not None]
    acc_corr = (sum(r["correct_correctness"] for r in subset)
                / len(subset) if subset else None)
    per_gold = {}
    for lab in ("ALLOW", "HOLD", "DENY"):
        rows = [r for r in records if r["gold"] == lab]
        if rows:
            per_gold[lab] = {
                "n": len(rows),
                "correct_operator": sum(r["correct_operator"]
                                        for r in rows),
                "accuracy_operator": sum(r["correct_operator"]
                                         for r in rows) / len(rows)}
    return {"n": n, "accuracy_operator": acc_op,
            "correctness": {"n": len(subset), "accuracy": acc_corr},
            "per_gold": per_gold, "items": records}


# ================= selftest (no model, no torch) =================

def run_selftest():
    cases = []

    def case(name, got, want):
        cases.append((name, got, want))

    case("extract bare", extract_outcome("ALLOW"), "ALLOW")
    case("extract lower", extract_outcome("hold"), "HOLD")
    case("extract sentence", extract_outcome("The answer is DENY."),
         "DENY")
    case("extract first wins", extract_outcome("HOLD, not ALLOW"),
         "HOLD")
    case("extract queued synonym", extract_outcome("queued"),
         "HOLD")
    case("extract denied synonym", extract_outcome("Denied."),
         "DENY")
    case("extract none", extract_outcome("no decision here"), None)
    case("extract empty", extract_outcome(""), None)
    case("extract boundary", extract_outcome("allowing is nice"),
         None)
    case("prompt shape", build_prompt("CTX"),
         "Governance decision.\nCTX\nAnswer with just ALLOW, "
         "HOLD, or DENY.")
    fake_items = [
        {"id": "t1", "gold": "ALLOW", "operator_correct": True,
         "correct_outcome": "ALLOW"},
        {"id": "t2", "gold": "ALLOW", "operator_correct": False,
         "correct_outcome": "HOLD"},
        {"id": "t3", "gold": "DENY", "operator_correct": None,
         "correct_outcome": None},
    ]
    res = score_records(fake_items, ["ALLOW", "ALLOW", "HOLD"])
    case("score n", res["n"], 3)
    case("score operator acc", res["accuracy_operator"], 2 / 3)
    case("score correctness n", res["correctness"]["n"], 2)
    case("score correctness acc", res["correctness"]["accuracy"],
         0.5)
    bad = 0
    for name, got, want in cases:
        ok = got == want
        if not ok:
            bad += 1
        print("%s: %s (got %r, want %r)"
              % ("ok" if ok else "FAIL", name, got, want))
    if bad:
        print("SELFTEST FAIL (%d/%d cases failed)"
              % (bad, len(cases)))
        return 1
    print("SELFTEST PASS (%d cases)" % len(cases))
    return 0


# ================= model-dependent scoring =================

def chat_text(tokenizer, prompt):
    msgs = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError as e:
        raise TypeError(
            "tokenizer.apply_chat_template rejected "
            "enable_thinking=False; refusing to fall back to a "
            "different prompt form: %s" % e) from e


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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="model directory")
    ap.add_argument("--battery", help="battery JSONL file "
                                      "(items carry `context`)")
    ap.add_argument("--out", help="output JSON path")
    ap.add_argument("--selftest", action="store_true",
                    help="exercise pure helpers on synthetic cases")
    args = ap.parse_args(argv)
    if args.selftest:
        return run_selftest()
    if not args.model or not args.battery:
        ap.error("--model and --battery are required "
                 "(unless --selftest)")
    with open(args.battery, encoding="utf-8") as fh:
        items = [json.loads(ln) for ln in fh if ln.strip()]
    splits = {}
    for it in items:
        splits.setdefault(it.get("split", "unknown"), []).append(it)
    tok, model, device, eos_ids = load_model(args.model)
    result = {"model": args.model, "battery": args.battery,
              "splits": {}}
    for split, rows in sorted(splits.items()):
        outputs = []
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            outputs.extend(generate_batch(
                tok, model, device,
                [build_prompt(b["context"]) for b in batch],
                eos_ids=eos_ids))
        res = score_records(rows, outputs)
        corr = res["correctness"]
        print("%s: accuracy_operator=%.4f (n=%d); "
              "accuracy_correctness=%s (n=%d)"
              % (split, res["accuracy_operator"], res["n"],
                 ("%.4f" % corr["accuracy"])
                 if corr["accuracy"] is not None else "n/a",
                 corr["n"]))
        result["splits"][split] = res
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
