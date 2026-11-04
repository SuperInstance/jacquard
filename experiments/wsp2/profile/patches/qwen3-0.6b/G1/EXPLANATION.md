# Qwen3-0.6B — G1 (format/completion) patch — EXPLANATION

Base: Qwen3-0.6B (tied embeddings; the base file stores both
copies of the embedding, and patch.py edits every stored copy).
Chained position: first patch in the sequence (base = pristine).
Diagnostic before: **18.33%** → after: **47.50%**. Dose: 61,440
stored scalars (30 critical + control rows counted once per stored
copy) = **0.00817%** of 751,632,384 stored parameters.

## Diagnosis (diagnostic split only, base outputs)

- copy_token 100% — the bare-answer contract already works when
  the answer is a single salient token.
- yes_no_compare 0/37 although the first generated token is the
  correct 'Yes'/'No' on most items: every reply continues into
  prose ("Yes, 68 is greater than 61."). First-token restricted
  argmax (Yes/No rows) = 0.73; Euclidean centroid on the
  answer-position hidden states = 0.92 — the readout separates,
  the *stopping* does not exist.
- small_add 0/34 and seq_next 0/24 are a different animal: at the
  answer position the best digit token is the FIRST OPERAND's
  first digit on 34/34 (small_add) and 19/24 (seq_next) items,
  the answer's first digit on 3/34 and 0/24. The sum is computed
  during generation (after an echoed equation), never present
  at the readout position — no row edit can make the model speak
  it first, and even perfect stopping leaves the echo prefix,
  which the strict matcher scores wrong. Declared unreachable
  by family 1 (see PATCHING-RECORD); no component targets it.
- EOS geometry (measured): at the answer position the top-1 vs
  EOS logit gap is 25–32, but the prompt-mean direction loses
  strength at continuation positions (cos(mu_prompt, mu_cont)
  = 0.24). A mean-direction EOS bias of +3.5/+11 (two early
  builds) changed nothing. The continuation-mean direction is
  selective: self-projection 80.6 at continuation states vs
  30.1 at the answer position.

## Components (all critical except controls)

- **format_stop** (E1–E2): EOS rows (151645, 151643) += alpha *
  continuation-mean direction, alpha set for +20 logits at
  continuation states (~+7 at the answer position, safely below
  the 24.9 minimum answer-position gap). Prediction: replies
  stop at the first completed answer.
- **yesno_readout** (E14–E15): E7 centroid direction+bias on the
  'Yes'/'No' rows from yes_no_compare class means, scale 0.03.
  Simulation on fixed hidden states: restricted accuracy
  0.73 → 0.92 at any scale ≥ 0.03 (the Euclidean ceiling).
  Scale 0.1 was tried first and collapsed generation (the
  E7 input-coupling failure: 'Yes'/'No' erupt mid-sequence) —
  that build is recorded in PATCHING-RECORD, not shipped.
- **digit_init** (E4–E13): digit rows '0'–'9' += +1.5 logits
  along the prompt-mean direction (E1's digit-first bias).
- **prose_suppress** (E3): 'The' row −6 logits (answer-position
  direction); no G1 answer begins with 'The', and 'The' was the
  dominant prose starter (19/120 first tokens).
- **controls** (E16–E30, non-critical): identical-form deltas on
  15 never-emitted special-token rows, declared in advance as
  the matched-count ablation control.

## Result by category (diagnostic)

copy_token 100→100, last_word 40→40, seq_next 0→4.17,
small_add 0→0 (unreachable, above), yes_no_compare 0→91.89
(the centroid ceiling, as predicted).

## E4 self-check (diagnostic)

Prediction: ablating the critical set kills the effect;
random same-norm directions in their place do not reproduce it.
Full 47.50 / minus-critical **18.33** (= base exactly) /
minus-random (seed 41) **17.50**. Holds exactly.
