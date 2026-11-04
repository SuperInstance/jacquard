# Qwen3-0.6B — G6 (unseparated relation) — NO PATCH declared

Chained diagnostic (after G3 patch): **50.0%** — the model
still answers ALLOW on every item, exactly as at base.
Probe evidence (diagnostic split, chained model):

- Class-mean separation at the answer position:
  ‖mu_c − mu‖ = **0.39** against ‖mu‖ = 167.5.
- Simulated family-1 row patch (E7 centroid direction+bias on
  the ALLOW / 'H' first-token rows): restricted accuracy
  **0.500 at every scale ≤ 1.0**, 0.533 at scale 2, 0.542 at
  scale 5. The Euclidean nearest-centroid ceiling is 0.60,
  and per REVIEW R2-F5 that residue is consistent with the
  battery's bimodal start-offset surface conjunction, not
  with the contention relation itself.
- Base logit gap ALLOW − 'H' is +4.42 (min +3.38): a patch
  would have to move logits by ~4.4 class-conditionally
  through a 0.39-norm direction.

An attempt at usable scale has a predicted effect of exactly
zero; an attempt at scale ≥ 2 buys ≤ 4 simulated points by
distorting the shared 'H' row (first token of every
H-initial word, and an input embedding) — distortion, not
readout repair. NO PATCH. This reproduces Phase 15's E8
finding on the profile's cleaner battery: the same-seat
contention relation is not separated in Qwen3-0.6B's
representation at any margin a row patch can use.
