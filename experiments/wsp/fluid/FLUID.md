# FLUID — context-only arm, Jacquard Phase 15 / slice 42 (E3, three poles)

**Intervention:** a frozen prompt package only (`prompt.json`): one short system
prompt + 8 hand-written few-shot pairs. No weights change. The package is
prepended to every battery item and scored as-is.

**Student:** Qwen3-0.6B. **Scorer contract (the design target):** the scorer
extracts the **last number** in the reply; generation is capped at **96 tokens**.
Base held-out is 80.5%; base validation is 83.5%. Evidence used: the 80-item
diagnostic split with base raw outputs (`diag_for_patcher.jsonl`). No held-out,
validation, or forgetting items were seen or sought.

## What the diagnostic actually shows

Reading all 80 base outputs, the failures are mostly *format* failures, not
*knowledge* failures:

1. **Truncation by verbosity (dominant class).** On `addsub_chain` the base
   model answers with markdown/LaTeX worked solutions ("### Step 1… $$…$$").
   The correct intermediate results are usually present, but the reply runs
   into the 96-token cap mid-final-step — e.g. diag-003/-005/-007/-009 all end
   with the final subtraction half-written ("…= 8", "…= 1", "…= 2"), so the
   last extracted number is a fragment of the answer. Validation: 48%.
2. **The comparison sentence trap.** On `compare` the base model's natural
   frame is "The number 8279 is larger than 1876" — the *correct* answer is
   stated first and the *loser* is the last number, so last-number extraction
   scores it wrong even when the model's judgement is right (diag-072, -073,
   -080; also -079 before its "Answer:" rescue line). A minority are genuine
   judgement inversions (diag-076, -077, -078), which no format can fix.
   Validation: 52%.
3. **2×2 multiplication slips, not verbosity.** Short `mul_2x2` replies often
   land (diag-021, -023, -029 correct), but direct one-shot products slip:
   51×37 → 1907 (gold 1887), 83×47 → 3941 (gold 3901), 74×85 → 6370 (gold
   6290). The model has no scratchpad habit for the hard case; it guesses the
   whole product in one step. Validation: 76%.
4. **Already-perfect categories** (`div_exact`, `mul_2x1`, `pct_of`,
   `unit_price`, and most `word_2step`): base outputs are longer but usually
   terminate inside the cap with the answer last. The risk here is
   *regression* if a new format disrupts them — the package must give these a
   compatible short form, not a foreign one.

## The chosen target format, and why

**One compact line of working, then stop: `step; step=answer`.** Bare-number-only
was rejected: it is the safest format for the scorer but throws away the
scratchpad a 0.6B model needs for 3-term chains and 2×2 products — the two
categories where it already slips arithmetically. Verbose chain-of-thought was
rejected for the opposite reason: it is exactly what the 96-token cap kills.
The middle form is deliberate:

- Each step is `numbers op numbers = result`, steps separated by `; `, all on
  one line, no words. A 3-term chain costs ~10 tokens; a decomposed 2×2
  product ~15 tokens. Nothing in the battery needs more than ~25 tokens in
  this format, so truncation becomes structurally impossible rather than
  merely unlikely.
- The **final step's result is the last token of the reply**, so last-number
  extraction gets the answer by construction. Intermediate numbers appearing
  earlier are harmless — only the last one is read.
- No "Answer:" label, no units, no $ signs, no restating the question: every
  such token is cap budget spent and, in the comparison case, a trap.
- **Comparisons are the one exception: bare number alone.** Any working or
  sentence frame for "which is larger" risks putting the loser last, and the
  task needs no arithmetic — selection only. Two few-shot pairs (one per
  surface phrasing, one where the *second* operand is larger) teach "output
  the winner, output nothing else", which also removes the truncation failure
  seen in diag-074 (a digit-by-digit comparison essay cut off at "Answer: 58").

## Element-by-element mapping

| Element | Targets |
|---|---|
| System prompt: "short working only — never sentences, explanations, headings, or $ signs, never repeat the question" | Failure 1 (verbosity/truncation); also suppresses the word-problem restatement habit that eats the cap on story items |
| System prompt: "the last number you write must be the answer… then stop" | The scorer contract stated in the model's own instruction channel; fights the model's urge to append a summary sentence after the answer (which would put question numbers last) |
| System prompt: "if only one step is needed, write just that step" | Protects the 100% categories (div, pct, unit price, 2×1) — gives them a legal short form (`621/9=69`) instead of forcing a two-step shape |
| System prompt + 2 few-shots: comparisons → larger number alone | Failure 2 (sentence trap + comparison-essay truncation) |
| Few-shots 1–2: two add/sub chains (pure `Compute:` surface + story surface), each shown as exactly two `; `-separated steps | Failure 1 on the weakest category (48%); the story variant teaches extracting the three operands in story order without narrating |
| Few-shots 5–6: two 2×2 multiplications, both decomposed as `a*(tens)=p; a*(ones)=q; p+q=answer` | Failure 3 — replaces one-shot product guessing with a 3-step scratchpad the 0.6B can actually execute; shown on both the bare `What is A * B?` surface and the rows-of-chairs story surface |
| Few-shots 7–8: two-step word problems (change-from-a-bill; pages-left) as `mul; sub=answer` | Keeps the already-decent `word_2step` behaviour but compresses it from ~60 tokens of LaTeX prose to ~8 tokens, removing its residual truncation risk (cf. diag-057 cut off inside `\boxed{12`) |
| All numbers hand-written, none copied from the diagnostic split | Required by the brief; also avoids teaching surface-specific answers instead of the format |

Prompt overhead is modest: a ~460-character system prompt and 8 short pairs
(~120 tokens of demonstrations), prepended identically to every item.

## What this cannot fix

- **Genuine arithmetic slips.** Decomposition lowers their rate on 2×2
  products and chains, but a 0.6B adding 1380+368 can still slip, and pct /
  unit-price items with decimals get no dedicated few-shot — they rely on the
  one-step rule generalising. A wrong intermediate poisons the final number
  exactly as surely as truncation did.
- **Genuine comparison inversions** (diag-076/-077/-078, where the model
  picked the smaller number). Format fixes extraction, not judgement; a bare
  wrong winner is still wrong.
- **Distribution shift in surfaces.** The few-shots cover the observed
  phrasings; a held-out surface far from these (e.g. comparisons embedded in a
  story) may pull the verbose habit back. The system prompt is the only
  defence there, and instruction-following at 0.6B is probabilistic — some
  fraction of replies will ignore the format regardless. That residual
  non-compliance rate is the arm's main uncertainty.

## Predicted held-out effect

Base held-out: **80.5%**. Authored-patch arm: **85.0%**.

**My honest prediction for this fluid arm: ~86% held-out (range 84–88%)** —
i.e. at or slightly above the patch arm.

Reasoning: the diagnostic says the recoverable mass is large and mechanical.
On validation, `compare` (52%) and `addsub_chain` (48%) together are where
nearly all the loss is, and in the diagnostic sample the majority of those
failures show the *correct value present in the reply* but unscorable
(truncated or not-last). The format removes both mechanisms almost entirely
for compliant replies, so those two categories should rise toward the model's
true judgement/arithmetic ceiling (~85–90% for comparisons given the observed
inversion rate; ~75–85% for chains given slip rates). `mul_2x2` gains more
modestly from decomposition (76% → ~82–85% expected). The 100% categories
should hold, because the one-step rule matches what the base model already
does when it succeeds. Against the patch arm: a weight patch can encode
"be terse" as a disposition, but it cannot as directly install the *specific*
decomposition procedure and the comparison exception; context can, verbatim,
on every item. The counterweight is compliance variance at 0.6B — if the
model ignores the package on ~10% of hard items, the arm lands at the low end
(~84%) and ties the patch instead of beating it. I do not predict above ~88%:
the genuine-slip and genuine-inversion residue is real, and no prompt gives a
0.6B model new arithmetic ability — it only stops the model from wasting the
ability it already has.
