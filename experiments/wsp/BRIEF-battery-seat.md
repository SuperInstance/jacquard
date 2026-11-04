BRIEF — battery builder seat (Jacquard Phase 15, slice 41)

You are building the experiment batteries and scoring harness
for a weight-space-programming study. You build instruments;
you do NOT patch any model, and you will never be shown the
patch work. Work in ~/jacquard-p15/experiments/wsp/ on this
machine (the Oracle). Everything deterministic and seeded.

CONTEXT (read first): experiments/wsp/PLAN.md in this repo
clone — especially the Batteries section. The model under
test is Qwen/Qwen3-0.6B; scoring runs later on the Thor GPU,
not here.

DELIVERABLES (all under experiments/wsp/):

1. gen_batteries.py — seeded generators writing:
   - batteries/diagnostic.jsonl  (80 arithmetic items)
   - batteries/validation.jsonl  (200 arithmetic items)
   - private/heldout.jsonl       (200 arithmetic items)
   - private/forget_instr.jsonl  (100 items)
   - private/forget_fact.jsonl   (100 items)
   - private/forget_prose.jsonl  (24 items, {"id","text"})
   Arithmetic categories (~equal proportions): addsub_chain,
   mul_2x1, mul_2x2, div_exact, pct_of, word_2step,
   unit_price, compare. Item: {"id","split","category",
   "prompt","answer","derivation"}; answer is a number;
   derivation is the worked expression (for graders only).
   Every prompt ends with the sentence
   "Answer with just the number."
   Diagnostic + validation use template set A and lexical
   pool A (names, objects, shops). Heldout uses a SEPARATE
   template set B and lexical pool B — different phrasings
   and surface forms for the same eight categories, written
   as distinct code, not parameter tweaks of set A.
   Number ranges: add/sub to 4 digits; mul_2x2 up to 99x99;
   div_exact always integer quotient; pct_of from
   {5,10,15,20,25,50,75} with bases giving integer results;
   all answers integers except unit_price may use exact
   2-decimal money values.
   forget_instr item: {"id","category","prompt","check":
   {"type":..., ...params}} with check types: json_key
   (reply parses as a JSON object containing the key),
   all_caps, starts_with {word}, ends_with {word},
   bullets3 (exactly 3 lines starting with "- "),
   word_count_range {lo,hi}. Prompts must be answerable
   by a small model in principle (simple content requests).
   forget_fact item: {"id","category","prompt","answer",
   "aliases":[...]} from fixed fact tables you author in
   the script: world capitals (30), chemical element
   symbols (25), solar-system facts (15), exact unit
   conversions (15), animal/geography misc (15). Short
   answers; aliases cover case/plural variants.
   forget_prose: 24 paragraphs, 60-90 words each, neutral
   descriptive prose you write inline in the script (no
   arithmetic, no instructions, no facts that matter).
2. verify_batteries.py — independent re-check: reparse each
   arithmetic item's derivation, recompute, assert equal
   to the stored answer; assert split files have expected
   counts; assert NO prompt string appears in more than
   one split; assert heldout prompts share no template
   marker with set A (check a list of set-A-only phrases
   you define); print a PASS/FAIL summary. Run it and
   leave its output in batteries/VERIFY.txt.
3. score.py — the scoring harness, run later on the Thor:
   `python3 score.py --model DIR --split NAME --out JSON`
   where NAME in {diagnostic, validation, heldout,
   forget_instr, forget_fact, forget_prose, all}.
   Loads the model with transformers (bf16; cuda if
   available else cpu), applies the chat template with
   thinking disabled (Qwen3: apply_chat_template(...,
   enable_thinking=False); guard for API differences),
   greedy decoding, batch 16, per-split max_new_tokens
   (arith 96, instr 128, fact 32). Arithmetic scoring:
   extract the LAST number in the completion (strip $, commas,
   %), compare to gold with abs tolerance 0.011 (money) /
   exact for integers. forget_instr: run the item's checker.
   forget_fact: normalised containment against answer or
   any alias. forget_prose: mean token NLL (teacher-forced,
   no generation). Output JSON: per-split overall accuracy
   (or mean NLL), per-category accuracy, and per-item
   records {id, category, gold, raw_output, extracted,
   correct}. Deterministic: no sampling anywhere.
   Also `--inspect` mode printing the model's config
   summary (layers, hidden size, vocab, tied embeddings,
   parameter count) as JSON.
4. BATTERIES.md — the design document: categories, counts,
   seeds, how sets A and B differ, checker definitions,
   the split discipline (who may see what), and the exact
   commands to regenerate and to score.

RULES: Python stdlib + (score.py only) torch/transformers.
No downloads. Do not modify anything outside
experiments/wsp/. Do not look at other phases' clones.
When done, print a summary: files written, verify result,
line counts. Your final message is the deliverable report.
