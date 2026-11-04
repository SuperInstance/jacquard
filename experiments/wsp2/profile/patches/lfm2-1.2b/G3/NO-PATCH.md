# LFM2-1.2B — G3 (readout) — NO PATCH declared

Chained diagnostic (after G2 patch): **60.83%** — the chain
had already lifted G3 from 32.5% (pristine base) by repairing
format (case_check 0→70, contains_letter 17.5→57.5). Two
authored attempts were built and scored on diagnostic; both
landed BELOW the chained base, so no patch is declared:

- Attempt 1 (vowel centroid s=0.1 + plural centroid s=0.05):
  **46.67%**. vowel_start 44.44→0 — outputs truncated to the
  first token ('con', 'v') by the inherited EOS pressure;
  length_compare 54.55→22.73 (the 'v'/'con' row deltas are
  also input embeddings inside prompt words); plural_check
  80→60.
- Attempt 2 (vowel s=0.08 + continuation-token boosts):
  **57.50%**. 'vowel' items complete and score; 'consonant'
  items still stop at 'con' ('son' never beat EOS after
  'con'); length_compare still damaged (40.91).

Probe facts behind the attempts: vowel_start separates in
simulation (restricted 0.44 → 0.89; Euclidean 0.94);
contains_letter does not (centroid 0.575, below the 0.70
majority rate); case_check shows no dot-product gain
(simulated flat 0.70). The vowel readout exists but cannot
be installed through the shared first-token rows without
losing the word-completion race to the chain's own EOS
edits and taxing length_compare. That is a boundary result,
not a tuning failure: two mechanism-distinct attempts are
on record with their failure modes.
