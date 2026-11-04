# Phase 17, W2 — cost ledger

Counted live, in the shape of Phase 16's accounting
(experiments/wsp2/FINDINGS.md §R4: battery construction
~12 min, round 1 ~12 min, round 2 ~16 min, 0 teacher calls,
two ~15-second coordinator scoring runs, 2 governance
proposals / 2 decisions; joint N+1 ≈ 1 hour end to end).

W2 window: 2026-11-04 18:48 → ~19:05 UTC (worker time, one
worker; start = task receipt, end = final push of this
ledger's commit).

| item | count / time |
|---|---|
| Worker minutes, total | ~30 min |
| — reading criteria / prior findings (CRITERIA, FINDINGS R4, SLICE43-E7, scorers) | ~5 min |
| — inventory counting (3 candidates, both boxes) | ~10 min |
| — battery build + leakage checks (script run) | < 1 min machine; ~4 min incl. writing builder |
| — incumbent scorer (writing + 2 runs) | ~3 min; runs < 1 s each |
| — student scorer (adaptation + selftest) | ~3 min |
| — documents (inventory, battery, this ledger) | ~5 min |
| Teacher calls | 0 |
| Student scoring runs | 1 (diagnostic only, zero-shot Qwen3-0.6B, 19.4 s wall on the Thor, 1,145 items) |
| Incumbent scoring runs | 2 (diagnostic + held-out, record alone) |
| Governance proposals / decisions by W2 | 0 / 0 (instructed: governance log untouched) |
| Downloads | 0 (bench model copy already on the Thor; record copies are local file copies, ~1.4 MB) |
| Thor resident state mutated | none (copies in ~/wsp-exp17/w2/ only; gpuq untouched, feeder stayed OFF) |

Comparison against the Phase 16 ~1 hour N+1 figure: W2's
inventory+battery+baselines slice cost ~30 worker-minutes —
inside the marginal-joint envelope (≈ half of it), and it
stopped there deliberately: the measured baselines
(incumbent 1.0000 both splits, student 1.0000 diagnostic)
show no patch round can earn the shadow bar on this joint,
so the round-1/round-2 spend (~28 min in Phase 16) was not
incurred. The saving is the finding's, not a shortcut: the
ledger for a future W2 round on a joint that clears the bar
should expect the full Phase 16 shape (≈ 12 + 12 + 16 min
plus scoring) on top of a comparable battery cost.
