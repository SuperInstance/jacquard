# LFM2-1.2B — G6 (unseparated relation) — NO PATCH declared

Chained diagnostic (after G2 patch): **0.00%** — and the
failure has changed shape: the chained model now answers
**'Yes' on G6 items** (the G1/G2 yes/no attractor captures
the answer position; the pristine base answered HOLD +
prose on every item, also 0.00% under the strict matcher).

Probe evidence (diagnostic split, chained model):

- Class-mean separation ‖mu_c − mu‖ = **0.76** against
  ‖mu‖ = 98.4 — the same order as Qwen3-0.6B's
  non-separation.
- Simulated row patch (ALLOW 'ALL' row 13644 / HOLD 'H'
  row 549): restricted accuracy 0.567 at scale 0.3,
  reaching the Euclidean ceiling 0.742 only at scale ≥ 1.
- The operative competition is not HOLD: the 'Yes' row
  beats ALLOW by **+8.0 logits on 120/120 items**. Even at
  scale 3, the correct label row beats 'Yes' on only
  27.5% of items; at usable scales, 0%.

A G6 patch here would have to out-shout an earlier grade's
patch through a 0.76-norm direction at scale 3–5 — row
vandalism on 'H' (first token of every H-initial word) for
a simulated ceiling of 0.75. NO PATCH. The grade's result
is two-layered: the relation is not separated (as with
Qwen), and the chain's own attractor is now the nearer
boundary — both recorded for the boundary map.
