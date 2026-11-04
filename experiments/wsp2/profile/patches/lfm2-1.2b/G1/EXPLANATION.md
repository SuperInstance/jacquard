# LFM2-1.2B — G1 (format/completion) patch — EXPLANATION

Base: LFM2-1.2B Q8_0 GGUF, loaded via the harness's GGUF route
(dequantised in memory); patch.py starts from that same loading
path and saves a complete standard model directory. The saved
directory was verified to load with plain `from_pretrained`
(the diagnostic score below was produced from the saved
directory) and reproduces the patch's scores.
Diagnostic before: **59.17%** → after: **87.50%**. Dose:
12,288 scalars = **0.00105%** of 1,170,340,608 parameters
(tied embeddings: one stored copy, edited once).

## Diagnosis (diagnostic split only, base outputs)

- small_add 100%, copy_token 100%, quoted-style numeric answers
  are single tokens in this vocabulary ('35' is one token) and
  the model already stops after them.
- yes_no_compare **0/37**: every reply's first word is the
  correct 'Yes'/'No', followed by ". Explanation: ..." prose.
  Answer-position geometry: Euclidean centroid 0.92, simulated
  row patch 0.78 → 0.92 at scale ≥ 0.1. Pure stopping +
  readout-calibration failure.
- seq_next 58.33%: the wrong items are bare wrong numbers —
  content, not format. Not targeted.
- last_word 60%: partly format ('Table' case is forgiven by
  the matcher), partly word choice. Not directly targeted;
  improved as a side effect of stopping (60→80).

## Components

- **format_stop** (E1, critical): EOS row (7, '<|im_end|>') +=
  alpha * continuation-mean direction, +15 logits at
  continuation states (continuation self-projection 48.0,
  answer-position projection 22.7 — selective by geometry).
- **yesno_readout** (E2–E3, critical): E7 centroid
  direction+bias on 'Yes' (12948) / 'No' (5048) rows from
  yes_no_compare class means, scale 0.1.
- **controls** (E4–E6, non-critical): same-form deltas on
  [PAD65530..65532] rows — never-emitted padding rows,
  declared in advance.

## Result by category (diagnostic)

copy_token 100→95 (one item lost to the stronger stop),
last_word 60→80, seq_next 58.33→58.33, small_add 100→100,
yes_no_compare 0→91.89 (the simulated ceiling).

## E4 self-check (diagnostic)

Full 87.50 / minus-critical **59.17** (= base exactly) /
minus-random (seed 41) **65.00** (yes_no_compare 18.92 vs 91.89
full — the effect follows the critical set; a random-direction
residue remains, recorded honestly: same-norm random deltas on
the Yes/No rows plus a randomised EOS delta stop some items
by chance).
