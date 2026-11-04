#!/usr/bin/env python3
"""Scoring harness for Jacquard Phase 15 batteries (runs on the Thor GPU).

Usage:
  python3 score.py --model DIR --split NAME --out results.json
  python3 score.py --inspect --model DIR
  python3 score.py --selftest

NAME in {diagnostic, validation, heldout, forget_instr, forget_fact,
forget_prose, all}. Battery files are resolved relative to this
script's own location (batteries/ and private/ subdirectories).

Greedy decoding only; no sampling anywhere. Greedy decoding is
not a guarantee of bitwise reproducibility: batch composition
and hardware may move plus-or-minus an item between runs.
The extraction / checker / NLL helpers below are pure stdlib
functions (importable without torch) and are exercised by
--selftest, which needs no model and no GPU.
"""
import argparse
import json
import math
import re
import string
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SPLIT_FILES = {
    "diagnostic": HERE / "batteries" / "diagnostic.jsonl",
    "validation": HERE / "batteries" / "validation.jsonl",
    "heldout": HERE / "private" / "heldout.jsonl",
    "forget_instr": HERE / "private" / "forget_instr.jsonl",
    "forget_fact": HERE / "private" / "forget_fact.jsonl",
    "forget_prose": HERE / "private" / "forget_prose.jsonl",
    "t2_diagnostic": HERE / "batteries" / "t2_diagnostic.jsonl",
    "t2_heldout": HERE / "private" / "t2_heldout.jsonl",
    "t3_diagnostic": HERE / "batteries" / "t3_diagnostic.jsonl",
    "t3_heldout": HERE / "private" / "t3_heldout.jsonl",
}
ARITH_SPLITS = {"diagnostic", "validation", "heldout",
                "t2_diagnostic", "t2_heldout",
                "t3_diagnostic", "t3_heldout"}
MAX_NEW_TOKENS = {"diagnostic": 96, "validation": 96, "heldout": 96,
                  "forget_instr": 128, "forget_fact": 32,
                  "t2_diagnostic": 96, "t2_heldout": 96,
                  "t3_diagnostic": 96, "t3_heldout": 96}
BATCH_SIZE = 16
MONEY_TOL = 0.011

# ================= pure helpers (no torch) =================

_NUMBER_RE = re.compile(r"-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")


def extract_last_number(text):
    """Last number in the text, as a float (None if there is none).

    Commas inside numbers are removed; surrounding $, % or words are
    ignored because the pattern matches the numeric core itself.
    Leading-dot decimals are accepted: ".75" (and "$.75") extract
    as 0.75. Known remaining edges (documented in BATTERIES.md,
    rule deliberately unchanged): fractions like "1/2" extract
    the last component number, ranges extract their last endpoint,
    and any trailing incidental number in the reply wins under the
    LAST-number rule.
    """
    matches = _NUMBER_RE.findall(text or "")
    if not matches:
        return None
    return float(matches[-1].replace(",", ""))


def arith_correct(extracted, gold):
    """Correct iff |extracted - gold| <= 0.011 (covers exact integers
    and 2-decimal money)."""
    if extracted is None:
        return False
    return abs(extracted - float(gold)) <= MONEY_TOL


def normalise_fact(text):
    """Lowercase, punctuation -> space, collapse whitespace."""
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fact_match(output, answer, aliases):
    """Token-boundary matching of the answer or any alias (F1).

    Both sides are normalised (lowercase, punctuation stripped).
    A candidate matches iff it appears as a complete token, or as
    a complete multi-token phrase (consecutive tokens), in the
    normalised reply. Substring matches never count: "paris"
    inside "comparison" is not a match, "12" is not "1", "fe" is
    not "c". Candidates shorter than 3 characters (e.g. element
    symbols "C", "H", "Na", counts "1", "8") therefore match ONLY
    as whole tokens -- the token rule is kept strict for them.
    """
    out_tokens = normalise_fact(output).split()
    if not out_tokens:
        return False
    for cand in [answer] + list(aliases or []):
        nc = normalise_fact(str(cand))
        if not nc:
            continue
        ctoks = nc.split()
        if len(ctoks) == 1:
            if ctoks[0] in out_tokens:
                return True
        else:
            n = len(ctoks)
            for i in range(len(out_tokens) - n + 1):
                if out_tokens[i:i + n] == ctoks:
                    return True
    return False


def check_json_key(text, key):
    s = (text or "").strip()
    obj = None
    try:
        obj = json.loads(s)
    except (ValueError, TypeError):
        i, j = s.find("{"), s.rfind("}")
        if 0 <= i < j:
            try:
                obj = json.loads(s[i:j + 1])
            except (ValueError, TypeError):
                obj = None
    return isinstance(obj, dict) and key in obj


def check_all_caps(text):
    s = (text or "").strip()
    return bool(s) and any(c.isalpha() for c in s) and s == s.upper()


def check_starts_with(text, word):
    s = (text or "").lstrip()
    if not s.startswith(word):
        return False
    rest = s[len(word):]
    return rest == "" or not rest[0].isalpha()


def check_ends_with(text, word):
    s = (text or "").strip()
    if not s:
        return False
    last = s.split()[-1].strip(string.punctuation)
    return last == word


def check_bullets3(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip() != ""]
    return len(lines) == 3 and all(ln.startswith("- ") for ln in lines)


def check_word_count_range(text, lo, hi):
    return lo <= len((text or "").split()) <= hi


def run_check(check, text):
    """Dispatch a forget_instr check object against a completion."""
    t = check.get("type")
    if t == "json_key":
        return check_json_key(text, check["key"])
    if t == "all_caps":
        return check_all_caps(text)
    if t == "starts_with":
        return check_starts_with(text, check["word"])
    if t == "ends_with":
        return check_ends_with(text, check["word"])
    if t == "bullets3":
        return check_bullets3(text)
    if t == "word_count_range":
        return check_word_count_range(text, check["lo"], check["hi"])
    raise ValueError(f"unknown check type {t!r}")


def mean_nll(logprobs):
    """Mean negative log-likelihood from per-token log-probs."""
    if not logprobs:
        return None
    return -sum(logprobs) / len(logprobs)

# ================= selftest (no model, no torch) =================

def run_selftest():
    cases = []

    def case(name, got, want):
        cases.append((name, got, want))

    # --- extraction edge cases ---
    case("extract $ with commas", extract_last_number(
        "The total is $1,234.50."), 1234.5)
    case("extract last of several", extract_last_number(
        "42 apples and then 7"), 7.0)
    case("extract percent", extract_last_number("25%"), 25.0)
    case("extract none", extract_last_number("no digits here"), None)
    case("extract negative", extract_last_number(
        "temperature -13 degrees"), -13.0)
    case("extract decimal then int", extract_last_number(
        "3.5 or 10"), 10.0)
    case("extract bare money", extract_last_number("$7.50"), 7.5)
    case("extract million commas", extract_last_number(
        "1,000,000"), 1000000.0)
    case("extract trailing prose", extract_last_number(
        "The answer is 3111 exactly."), 3111.0)
    case("extract leading dot", extract_last_number(".75"), 0.75)
    case("extract dollar leading dot", extract_last_number(
        "$.75"), 0.75)
    case("extract plain decimal", extract_last_number("0.75"), 0.75)

    # --- arithmetic comparison ---
    case("arith int exact", arith_correct(3111.0, 3111), True)
    case("arith money exact", arith_correct(2.5, 2.5), True)
    case("arith money off by cent", arith_correct(2.51, 2.5), True)
    case("arith money wrong", arith_correct(2.52, 2.5), False)
    case("arith int wrong", arith_correct(3112.0, 3111), False)
    case("arith none", arith_correct(None, 5), False)

    # --- json_key ---
    case("json_key plain", check_json_key(
        '{"color": "blue"}', "color"), True)
    case("json_key embedded", check_json_key(
        'Here you go: {"city": "Oslo"} done', "city"), True)
    case("json_key wrong key", check_json_key(
        '{"a": 1}', "color"), False)
    case("json_key not json", check_json_key(
        "the colour is blue", "color"), False)

    # --- all_caps ---
    case("all_caps ok", check_all_caps("HELLO WORLD"), True)
    case("all_caps mixed", check_all_caps("Hello"), False)
    case("all_caps digits only", check_all_caps("123"), False)

    # --- starts_with / ends_with ---
    case("starts_with ok", check_starts_with(
        "The sea is calm.", "The"), True)
    case("starts_with case", check_starts_with(
        "the sea is calm.", "The"), False)
    case("starts_with boundary", check_starts_with(
        "Theatre is fun", "The"), False)
    case("ends_with ok", check_ends_with(
        "We are going home", "home"), True)
    case("ends_with full stop", check_ends_with(
        "We are going home.", "home"), True)
    case("ends_with partial word", check_ends_with(
        "the homeward road", "home"), False)

    # --- bullets3 ---
    case("bullets3 ok", check_bullets3(
        "- apples\n- pears\n- plums"), True)
    case("bullets3 two", check_bullets3("- a\n- b"), False)
    case("bullets3 four", check_bullets3(
        "- a\n- b\n- c\n- d"), False)
    case("bullets3 plain line", check_bullets3(
        "a\n- b\n- c"), False)

    # --- word_count_range ---
    case("wcr in range", check_word_count_range(
        "one two three four five", 5, 10), True)
    case("wcr too few", check_word_count_range(
        "one two", 5, 10), False)
    case("wcr too many", check_word_count_range(
        "one two three four five six", 5, 5), False)

    # --- fact matching ---
    case("fact plain", fact_match(
        "The capital is Paris.", "Paris", []), True)
    case("fact multiword", fact_match(
        "The answer is New Delhi.", "New Delhi", ["Delhi"]), True)
    case("fact alias", fact_match(
        "The Pacific.", "Pacific Ocean", ["Pacific"]), True)
    case("fact wrong", fact_match(
        "Oslo is the capital.", "Paris", []), False)
    case("fact punctuation", fact_match(
        "It is Paris, France.", "Paris", []), True)
    # --- F1 adversarial: these must FAIL matching ---
    case("fact adversarial carbon/Fe", fact_match(
        "The chemical symbol for carbon is Fe", "C", []), False)
    case("fact adversarial know/H", fact_match(
        "I do not know", "H", []), False)
    case("fact adversarial moons/1", fact_match(
        "Earth has 12 moons", "1", []), False)
    case("fact adversarial comparison/Paris", fact_match(
        "No comparison is possible", "Paris", []), False)
    case("fact adversarial substring token", fact_match(
        "The cat sat there", "C", []), False)
    # --- F1 positive controls for short candidates ---
    case("fact short symbol ok", fact_match(
        "The symbol is C.", "C", []), True)
    case("fact short count ok", fact_match(
        "Earth has 1 moon", "1", []), True)

    # --- run_check dispatch ---
    case("dispatch bullets3", run_check(
        {"type": "bullets3"}, "- a\n- b\n- c"), True)
    case("dispatch word_count_range", run_check(
        {"type": "word_count_range", "lo": 2, "hi": 3},
        "two words"), True)

    # --- NLL math ---
    case("mean_nll basic", mean_nll([0.0, -2.0]), 1.0)
    case("mean_nll empty", mean_nll([]), None)

    bad = 0
    for name, got, want in cases:
        ok = got == want
        if not ok:
            bad += 1
        print(f"{'ok' if ok else 'FAIL'}: {name} "
              f"(got {got!r}, want {want!r})")
    if bad:
        print(f"SELFTEST FAIL ({bad}/{len(cases)} cases failed)")
        return 1
    print(f"SELFTEST PASS ({len(cases)} cases)")
    return 0

# ================= model-dependent scoring =================

def load_items(split):
    with SPLIT_FILES[split].open(encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def chat_text(tokenizer, prompt):
    msgs = [{"role": "user", "content": prompt}]
    try:
        return tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError as e:
        # N5: an instrument must fail loudly, never silently change
        # the prompt by dropping the thinking flag.
        raise TypeError(
            "tokenizer.apply_chat_template rejected "
            "enable_thinking=False; refusing to fall back to a "
            f"different prompt form: {e}") from e


def collect_eos_ids(model_dir, tok):
    """Union of eos ids from the model dir's generation_config.json
    (if present) and the tokenizer's eos (N5)."""
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


def generate_batch(tok, model, device, prompts, max_new,
                   eos_ids=None):
    import torch
    texts = [chat_text(tok, p) for p in prompts]
    enc = tok(texts, return_tensors="pt", padding=True).to(device)
    # N5: pass eos_token_id explicitly -- the union collected from
    # generation_config.json and the tokenizer (single int if one
    # id, list if several).
    eos_arg = None
    if eos_ids:
        eos_arg = eos_ids[0] if len(eos_ids) == 1 else list(eos_ids)
    with torch.no_grad():
        out = model.generate(
            **enc, max_new_tokens=max_new, do_sample=False,
            num_beams=1, pad_token_id=tok.pad_token_id,
            eos_token_id=eos_arg)
    gen = out[:, enc["input_ids"].shape[1]:]
    return [tok.decode(row, skip_special_tokens=True) for row in gen]


def score_generation_split(tok, model, device, split, eos_ids=None):
    items = load_items(split)
    outputs = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        outputs.extend(generate_batch(
            tok, model, device, [b["prompt"] for b in batch],
            MAX_NEW_TOKENS[split], eos_ids=eos_ids))
    records, per_cat = [], {}
    for it, raw in zip(items, outputs):
        if split in ARITH_SPLITS:
            extracted = extract_last_number(raw)
            gold = it["answer"]
            correct = arith_correct(extracted, gold)
        elif split == "forget_instr":
            extracted = None
            gold = it["check"]
            correct = run_check(it["check"], raw)
        elif split == "forget_fact":
            extracted = None
            gold = it["answer"]
            correct = fact_match(raw, it["answer"], it.get("aliases"))
        else:
            raise ValueError(split)
        records.append({"id": it["id"], "category": it["category"],
                        "gold": gold, "raw_output": raw,
                        "extracted": extracted, "correct": correct})
        c = per_cat.setdefault(it["category"], [0, 0])
        c[1] += 1
        c[0] += 1 if correct else 0
    n = len(records)
    acc = sum(r["correct"] for r in records) / n if n else 0.0
    return {"n": n, "accuracy": acc,
            "per_category": {k: {"correct": v[0], "n": v[1],
                                 "accuracy": v[0] / v[1]}
                             for k, v in sorted(per_cat.items())},
            "items": records}


def score_prose_split(tok, model, device):
    import torch
    import torch.nn.functional as F
    items = load_items("forget_prose")
    records, nlls = [], []
    for it in items:
        ids = tok(it["text"], return_tensors="pt")["input_ids"].to(device)
        with torch.no_grad():
            logits = model(ids, use_cache=False).logits
        logp = F.log_softmax(logits[0, :-1].float(), dim=-1)
        tgt = ids[0, 1:]
        token_lp = logp.gather(1, tgt.unsqueeze(1)).squeeze(1)
        nll = mean_nll([float(x) for x in token_lp.tolist()])
        nlls.append(nll)
        records.append({"id": it["id"], "category": "prose",
                        "gold": None, "raw_output": "",
                        "extracted": nll, "correct": None})
    overall = sum(nlls) / len(nlls) if nlls else None
    return {"n": len(records), "mean_nll": overall,
            "per_category": {"prose": {"n": len(records),
                                       "mean_nll": overall}},
            "items": records}


def inspect_model(model_dir):
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(model_dir)
    info = {
        "num_hidden_layers": getattr(cfg, "num_hidden_layers", None),
        "hidden_size": getattr(cfg, "hidden_size", None),
        "vocab_size": getattr(cfg, "vocab_size", None),
        "tie_word_embeddings": getattr(cfg, "tie_word_embeddings",
                                       None),
        "num_attention_heads": getattr(cfg, "num_attention_heads",
                                       None),
        "num_key_value_heads": getattr(cfg, "num_key_value_heads",
                                       None),
        "max_position_embeddings": getattr(
            cfg, "max_position_embeddings", None),
        "parameter_count": None,
    }
    # Parameter count from safetensors headers (no full load).
    try:
        from safetensors import safe_open
        total = 0
        for shard in sorted(Path(model_dir).glob("*.safetensors")):
            with safe_open(str(shard), framework="pt") as f:
                for key in f.keys():
                    shape = f.get_slice(key).get_shape()
                    total += math.prod(shape)
        info["parameter_count"] = total if total else None
    except Exception:  # noqa: BLE001
        info["parameter_count"] = None
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="model directory")
    ap.add_argument("--split", default="all",
                    choices=list(SPLIT_FILES) + ["all"])
    ap.add_argument("--out", help="output JSON path")
    ap.add_argument("--inspect", action="store_true",
                    help="print model config summary JSON and exit")
    ap.add_argument("--selftest", action="store_true",
                    help="exercise pure helpers on synthetic cases")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.model:
        ap.error("--model is required (unless --selftest)")
    if args.inspect:
        print(json.dumps(inspect_model(args.model), indent=2))
        return 0

    splits = list(SPLIT_FILES) if args.split == "all" else [args.split]
    tok, model, device, eos_ids = load_model(args.model)
    result = {"model": args.model, "splits": {}}
    for split in splits:
        if split == "forget_prose":
            res = score_prose_split(tok, model, device)
            print(f"{split}: mean_nll={res['mean_nll']:.4f} "
                  f"(n={res['n']})")
        else:
            res = score_generation_split(tok, model, device, split,
                                         eos_ids=eos_ids)
            print(f"{split}: accuracy={res['accuracy']:.4f} "
                  f"(n={res['n']})")
        result["splits"][split] = res
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
