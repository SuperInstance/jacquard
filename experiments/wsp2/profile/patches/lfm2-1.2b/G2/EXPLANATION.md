# LFM2-1.2B — G2 (framing) patch — EXPLANATION

Base: the chained G1 patch output (a standard directory saved
from the GGUF route). Diagnostic (chained base) **63.33%** →
after: **72.50%**. Dose: 8,192 scalars = **0.00070%**.

## Diagnosis (diagnostic split, chained model)

The G1 patch already lifted G2 from 33.33 (pristine base) to
63.33: quoted_question 100%, not_category 100%. Remaining:
false_claim 45.24%, order_swap 48.65%, distractor 60%.

Frame geometry (chained hidden states): the two yes/no frames
must be probed separately — pooled, their centroids cancel
(simulated 0.53–0.57). Per category: false_claim centroid
simulates 0.45 → 0.88, order_swap 0.68 → 0.92. But the two
frame deltas CONFLICT on the shared Yes/No rows (cross-
simulation: joint application leaves order_swap at 0.59,
below its 0.68 base; false_claim-alone costs order_swap
0.68 → 0.59; order_swap-alone is false_claim-neutral).
order_swap's other loss is initiation: a third of its items
begin with the prose starter 'To' ("To determine if ...").

## Components (final)

- **falseclaim_readout** (E1–E2, critical): centroid
  direction+bias on 'Yes'/'No' rows, class means from
  false_claim items only, scale **0.04**.
- **controls** (E3–E4, non-critical): [PAD65533..65534] rows.

## Why scale 0.04 (the knife-edge finding)

Candidate 1 (false_claim scale 0.1 + 'To' suppression −4)
hit the G2 target harder (79.17; false_claim 88.10) but G1
diagnostic retention fell 87.50 → 65.83. Candidate 2 (this
patch) reaches G2 72.50 with G1 retention 71.67. In BOTH
variants G1's yes_no_compare falls to exactly 45.95: the G1
plain-compare readout sits on a calibration ridge (the E7
phenomenon), and any claim-frame delta, at any tested dose,
flips its regime. The interference is not dose-shaped; it is
geometry-shaped — the two frames' readouts cannot coexist on
two shared rows. Candidate 2 is declared final as the
retention-respecting point; candidate 1's numbers are in
PATCHING-RECORD.

## Result by category (diagnostic)

distractor 60→40 (n=5), false_claim 45.24→64.29,
not_category 100→100, order_swap 48.65→59.46,
quoted_question 100→100.

## E4 self-check (diagnostic)

Full 72.50 / minus-critical **63.33** (= chained base exactly)
/ minus-random (seed 41) **65.00** (false_claim back to 45.24
in both ablations). The effect follows the critical set.
