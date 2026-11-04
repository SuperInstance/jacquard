# Slice 42 (part 1) — E3: the three poles on one target failure

Same student (Qwen3-0.6B), same target (the arithmetic battery),
same information budget (the 80-item diagnostic split), same
instrument (fixed harness, 96-token cap, last-number extraction).
Base: validation 83.5%, heldout 80.5%, forget_instr 81%,
forget_fact 85%, prose NLL 4.0688.

## Results

| pole | validation | heldout | forget_instr | forget_fact | prose NLL |
|---|---|---|---|---|---|
| base | 83.5 | 80.5 | 81 | 85 | 4.0688 |
| FLUID (context only) | 77.0 | 78.5 | 84 | **9** | = base* |
| GRADIENT (LoRA) | 59.5 | 48.0 | 84 | 87 | 3.9912 |
| YANG (authored patch) | 91.5 | 85.0 | 81 | 85 | 4.0739 |

*The fluid arm changes no weights; its prose NLL is the base
model's by construction. Everywhere the package is NOT applied,
the fluid pole changes nothing at all — and everywhere it IS
applied, it changes everything below.

## The fluid pole (prompt package, fluid/prompt.json)

A system prompt + 8 hand-written few-shots teaching one compact
format ("step; step=answer", answer last). Where the format
fits, it is excellent: heldout addsub_chain 48% -> 88%
(chains stop truncating), compare holds 100%, mul_2x2 44% -> 64%.
But a context is a GLOBAL instrument — it cannot be scoped to
the task it was written for:
- unit_price collapses (heldout 72% -> 12%): the few-shot
  surface patterns mislead money-division items into wrong
  compact procedures ("31.50 - 3 = 28.50" for a unit price).
- word_2step falls 84% -> 72%.
- forget_fact craters 85% -> 9%: applied to fact questions,
  the package's numeric prior overrides retrieval entirely —
  the model answers "47" to every capital asked. Capitals,
  elements, solar system: 0%.
- forget_instr nets +3 while churning internally
  (ends_with 47% -> 88%, word_count_range 38% -> 12%).
The author's prediction was ~86% heldout; the arm landed at
78.5%, BELOW base. The miss is the finding: context adaptation
is powerful exactly where it applies and indiscriminate
exactly there too. (A deployment could route contexts per
task — at the price of becoming a per-task artefact manager,
which is the yang pole's job description arriving by the
back door.)

## The gradient pole (LoRA, pre-registered recipe)

r16/alpha32 on all projections + MLPs, lr 1e-4, 3 epochs on
the 80 diagnostic items with bare-answer targets, completion-
only loss, merged. Train loss fell (1.09 avg, 0.37 final) and
the result is a catastrophe with a clean mechanism: median
output length 3 characters (base: 136.5). The model learned
the training signal's FORM perfectly — emit one bare number
immediately — and the numbers are close-but-wrong one-shot
guesses (1443 for 1387, 8160 for 8534); 29 of 30 diagnostic
failures are wrong-and-short. The base model's arithmetic
lives in its chain-of-thought; training on bare answers
amputated the scaffold the capability stood on. Heldout
80.5% -> 48.0%. Its forgetting profile is perversely good
(instr 84, fact 87, prose NLL improved to 3.9912): the damage
is task-local — it did not get globally dumber, it got
specifically worse at the thing it was trained on, because
the training specification (bare golds) was an impoverished
description of the task. Fairness notes, stated plainly: one
recipe, fixed in advance; a CoT-preserving LoRA (worked-
solution targets) is a DIFFERENT, larger information budget
— the patcher's advantage was precisely that it needed no
such supervision, because it could reason about the
procedure instead of fitting the form.

## The yang pole (authored patch, slice 41)

Heldout 85.0% (+4.5), validation 91.5% (+8.0), forgetting
identical to base. Its gain came from diagnosing that the
failure was completion, not capability, and editing the
logit geometry of answer initiation while PRESERVING a
compact scaffold ("7014 + 673 = 7687; 7687 - 6300 = 1387")
— the middle path neither pole found: fluid imposed a
format from outside the weights and paid for it everywhere
else; gradient fitted the format and lost the procedure;
the patch changed the model's own disposition toward the
format, scoped by content (digit-initiation contexts),
leaving everything else measurably untouched.

## Auditability — scored as strictly as accuracy

The charter's question for each pole: can the artefact
answer "what changed, why, on whose authority, how is it
undone?"
- FLUID: what changed is fully enumerable (a 1.8 KB text)
  but what it DOES is not — its effect is the whole model's
  behaviour under that context, discoverable only by
  measurement (nobody predicted unit_price or the "47"s
  from reading the package; its own author predicted +5.5
  and got -2). Why: a design rationale exists (FLUID.md).
  Undo: delete the package — instant and total. Authority:
  sealable as a hash, but the artefact is a RECIPE whose
  effect depends on the runtime that applies it.
- GRADIENT: what changed is a ~6.4M-scalar adapter — a file
  you can hash and cannot read. Why: nothing in the artefact
  records a reason for any scalar; the rationale is "the
  loss went down," and here the loss going down WAS the
  failure. Undo: drop the adapter (clean unmerged; the
  merged copy requires keeping the base). Authority: the
  training run's config + data are sealable, but the mapping
  from them to the artefact is an optimiser trajectory, not
  a decision.
- YANG: what changed is 44 edit records — enumerable,
  priced (43,028 scalars), each with a stated mechanism,
  and the mechanism claims were ABLATION-VERIFIED (slice
  41 E4: minus-critical = base exactly, minus-random =
  full exactly). Undo: do not apply patch.py; the base was
  never modified. Authority: the artefact IS the change —
  hash it and you have sealed the intervention itself, not
  a recipe for one.
On the evidence of this slice: the poles differ less in
power than in what kind of object they leave behind. Only
the yang pole leaves an artefact that is simultaneously
the intervention, its explanation, and its own undo.
