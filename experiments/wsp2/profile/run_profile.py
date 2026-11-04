#!/usr/bin/env python3
"""Patchability-profile harness.

Scores a model against the six graded batteries in batteries/
(G1 format/completion, G2 framing, G3 readout, G4 procedure,
G5 factor-knowledge, G6 unseparated relation) and emits a
machine-readable results JSON with per-item records.

Modes:
  base      Score one model on every grade x split.
              python3 run_profile.py --model DIR --out results.json
  sequence  Run the profile in grade order with patched model
            directories, producing the task-held-out retention
            structure: after each grade's patch, the HELD-OUT sets
            of all previously profiled grades are re-scored with
            the patched model.
              python3 run_profile.py --model BASE_DIR \
                  --patch G1=DIR --patch G3=DIR --out seq.json
            Grades without a --patch entry keep the previous model
            in the chain (the row records which model was scored).
  selftest  Exercise the pure scorer helpers (no model, no GPU).
              python3 run_profile.py --selftest

Scoring discipline (inherited from the Phase 15 harness):
  - greedy decoding only, no sampling;
  - the model's chat template is applied with thinking disabled;
    if the tokenizer rejects that keyword the run stops loudly --
    an instrument must never silently change its prompts;
  - the prompt for an item is exactly its battery text, fixed at
    generation time;
  - eos ids are the union of the model directory's
    generation_config.json ids (when present) and the tokenizer's
    eos id;
  - every item's raw output is saved in the results JSON.

Matcher: exact normalised-answer matching. Normalisation is:
lowercase; strip; collapse internal whitespace to single spaces;
remove thousands commas; remove one trailing full stop; map the
Unicode minus to '-'; fold accents (NFKD decomposition, combining
marks removed) so a correctly accented reply ("Bogotá") matches
an ASCII-folded gold ("Bogota") and vice versa. If both the
normalised reply and the gold parse as numbers, they are compared
as numbers (so "07" matches "7" and "11.0" matches "11"). NOTHING
else is forgiven: a reply that merely CONTAINS the gold string
scores wrong. This is deliberately stricter than substring/token
matching -- a reply is an answer only if it is the whole reply.
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATTERIES = HERE / "batteries"
GRADES = ["G1", "G2", "G3", "G4", "G5", "G6"]
SPLITS = ["diagnostic", "validation", "heldout"]
MAX_NEW_TOKENS = 32
BATCH_SIZE = 16


# ================= pure helpers (no torch) =================

def normalise_answer(text):
    t = (text or "").strip().lower()
    # Accent-fold: NFKD decomposition separates base letters from
    # combining marks; dropping the marks maps "bogotá" -> "bogota"
    # on BOTH the reply and the gold, so correct accents are never
    # discredited against ASCII-folded golds (review fix R2-F1).
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("−", "-").replace(",", "")
    t = re.sub(r"\s+", " ", t)
    if t.endswith("."):
        t = t[:-1]
    return t.strip()


def _as_number(t):
    try:
        return float(t)
    except (TypeError, ValueError):
        return None


def is_correct(raw_output, gold):
    """Exact normalised-answer match (see module docstring)."""
    n_out, n_gold = normalise_answer(raw_output), normalise_answer(gold)
    if n_out == n_gold:
        return True
    a, b = _as_number(n_out), _as_number(n_gold)
    return a is not None and b is not None and a == b


def load_items(grade, split):
    path = BATTERIES / f"{grade.lower()}_{split}.jsonl"
    return [json.loads(l) for l in open(path) if l.strip()]


def summarise(records):
    by_cat = defaultdict(lambda: [0, 0])
    for r in records:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += int(r["correct"])
    n = len(records)
    correct = sum(r["correct"] for r in records)
    return {"n": n, "correct": correct,
            "accuracy": round(100.0 * correct / n, 2) if n else None,
            "per_category": {c: {"n": v[1], "correct": v[0],
                                 "accuracy": round(100.0 * v[0] / v[1], 2)}
                             for c, v in sorted(by_cat.items())},
            "items": records}


# ================= model side =================

def load_model(model_path):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    p = Path(model_path)
    kwargs = {}
    if p.is_file() and p.suffix == ".gguf":
        tok = AutoTokenizer.from_pretrained(str(p.parent),
                                            gguf_file=p.name)
        model = AutoModelForCausalLM.from_pretrained(
            str(p.parent), gguf_file=p.name, dtype=torch.bfloat16)
    else:
        tok = AutoTokenizer.from_pretrained(str(p))
        model = AutoModelForCausalLM.from_pretrained(
            str(p), dtype=torch.bfloat16)
    # Batched generation requires LEFT padding: with right padding,
    # rows in a batch start generating at different offsets and the
    # continuation slice is wrong for every shorter prompt (an
    # earlier version of this harness produced empty outputs that
    # way; the fix is recorded in the builder's log).
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token_id = tok.eos_token_id
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()
    return model, tok, device


def eos_ids(model_path, tok):
    ids = set()
    p = Path(model_path)
    cfg = (p / "generation_config.json") if p.is_dir() else None
    if cfg and cfg.exists():
        data = json.loads(cfg.read_text())
        v = data.get("eos_token_id")
        if isinstance(v, int):
            ids.add(v)
        elif isinstance(v, list):
            ids.update(v)
    if tok.eos_token_id is not None:
        ids.add(tok.eos_token_id)
    return sorted(ids)


def render_prompt(tok, text):
    try:
        return tok.apply_chat_template(
            [{"role": "user", "content": text}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
    except TypeError as e:
        raise TypeError(
            "tokenizer rejected enable_thinking=False; refusing to "
            "fall back silently (the prompt would change)") from e


def score_items(model, tok, device, items, eos):
    import torch
    records = []
    prompts = [render_prompt(tok, it["prompt"]) for it in items]
    for i in range(0, len(items), BATCH_SIZE):
        batch_items = items[i:i + BATCH_SIZE]
        batch_prompts = prompts[i:i + BATCH_SIZE]
        enc = tok(batch_prompts, return_tensors="pt", padding=True,
                  add_special_tokens=False).to(device)
        with torch.no_grad():
            out = model.generate(
                **enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                eos_token_id=eos if len(eos) != 1 else eos[0],
                pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j, it in enumerate(batch_items):
            gen = out[j][enc["input_ids"].shape[1]:]
            raw = tok.decode(gen, skip_special_tokens=True)
            records.append({
                "id": it["id"], "category": it["category"],
                "gold": it["answer"], "raw_output": raw,
                "normalised_output": normalise_answer(raw),
                "correct": is_correct(raw, it["answer"])})
    return records


def score_grade(model, tok, device, eos, grade, splits):
    return {split: summarise(score_items(
        model, tok, device, load_items(grade, split), eos))
        for split in splits}


# ================= modes =================

def run_base(model_path):
    model, tok, device = load_model(model_path)
    eos = eos_ids(model_path, tok)
    result = {"mode": "base", "model": str(model_path),
              "device": device, "eos_token_ids": eos,
              "max_new_tokens": MAX_NEW_TOKENS,
              "grades": {}}
    for grade in GRADES:
        result["grades"][grade] = score_grade(
            model, tok, device, eos, grade, SPLITS)
        acc = {s: result["grades"][grade][s]["accuracy"] for s in SPLITS}
        print(f"{grade}: {acc}", flush=True)
    return result


def run_sequence(base_path, patches):
    """patches: dict grade -> model dir. Retention rows are emitted
    in profile order; each row re-scores the held-out split of every
    grade profiled so far with the current model in the chain."""
    chain = {}  # grade -> model path in force after that grade
    current = str(base_path)
    rows = []
    results = {"mode": "sequence", "base_model": str(base_path),
               "patches": patches, "stages": [], "retention_curve": []}
    # stage 0: base model on every grade's held-out set
    model, tok, device = load_model(base_path)
    eos = eos_ids(base_path, tok)
    base_held = {}
    for grade in GRADES:
        base_held[grade] = summarise(score_items(
            model, tok, device, load_items(grade, "heldout"), eos))
    rows.append({"after_grade": None, "model": str(base_path),
                 "heldout_accuracy": {g: base_held[g]["accuracy"]
                                      for g in GRADES}})
    results["stages"].append({"stage": "base", "model": str(base_path),
                              "heldout": base_held})
    del model
    profiled = []
    for grade in GRADES:
        profiled.append(grade)
        if grade in patches:
            current = patches[grade]
        model, tok, device = load_model(current)
        eos = eos_ids(current, tok)
        stage = {"stage": f"after_{grade}", "model": current,
                 "own_grade": score_grade(model, tok, device, eos,
                                          grade, SPLITS),
                 "heldout": {}}
        for prev in profiled:
            stage["heldout"][prev] = summarise(score_items(
                model, tok, device, load_items(prev, "heldout"), eos))
        rows.append({"after_grade": grade, "model": current,
                     "heldout_accuracy": {
                         g: stage["heldout"][g]["accuracy"]
                         for g in profiled}})
        results["stages"].append(stage)
        print(f"after {grade} ({current}): "
              f"{rows[-1]['heldout_accuracy']}", flush=True)
        del model
    results["retention_curve"] = rows
    return results


def selftest():
    cases = [
        ("42", "42", True), (" 42 ", "42", True), ("42.", "42", True),
        ("07", "7", True), ("11.0", "11", True), ("1,000", "1000", True),
        ("Paris", "paris", True), ("New  Delhi", "New Delhi", True),
        ("ALLOW", "allow", True), ("Fe", "Fe", True),
        # accent behaviour, both directions (R2-F1)
        ("Malé", "Male", True), ("Male", "Malé", True),
        ("Bogotá", "Bogota", True), ("Bogota", "Bogotá", True),
        ("Brasília", "Brasilia", True), ("Asunción", "Asuncion", True),
        ("Reykjavík", "Reykjavik", True), ("Bogotá", "Cairo", False),
        # must NOT credit incidental containment (Phase 15 defect class)
        ("The answer is 42", "42", False),
        ("Paris is the capital", "Paris", False),
        ("42 or 43", "42", False), ("Fe is iron", "Fe", False),
        ("I think yes", "yes", False), ("", "42", False),
        ("43", "42", False), ("hold on", "HOLD", False),
    ]
    ok = True
    for raw, gold, want in cases:
        got = is_correct(raw, gold)
        mark = "PASS" if got == want else "FAIL"
        ok &= got == want
        print(f"{mark}: is_correct({raw!r}, {gold!r}) = {got} (want {want})")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="model directory or .gguf file")
    ap.add_argument("--patch", action="append", default=[],
                    metavar="GRADE=DIR",
                    help="patched model dir for a grade (sequence mode)")
    ap.add_argument("--out", help="results JSON path")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.model or not args.out:
        ap.error("--model and --out are required (or use --selftest)")
    if args.patch:
        patches = dict(kv.split("=", 1) for kv in args.patch)
        result = run_sequence(args.model, patches)
    else:
        result = run_base(args.model)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
