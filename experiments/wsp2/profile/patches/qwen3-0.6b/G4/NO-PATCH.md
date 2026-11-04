# Qwen3-0.6B — G4 (procedure) — NO PATCH declared

Chained diagnostic (after G3 patch): **0.00%** in every
category. Probe evidence (diagnostic split, chained model):

- At the answer position, the best digit token is the FIRST
  PROMPT NUMBER's first digit on 17–20 of ~20 items in every
  category (weekday_offset 20/20, month_span 17/17). The
  answer's own first digit is the readout's best digit on
  1–5 items per category — chance level.
- Base-model outputs compute in prose and are mostly wrong
  even there (a 21-day gap answered as 10 days; the builder's
  lenient last-number check would credit only 12/120 held-out
  items — recorded in SLICE45-BUILD.md, not re-measured here).

Multi-step date/week arithmetic is not present at the readout
position in any linearly usable form; it happens, when it
happens, inside generation. A family-1 row patch has nothing
to aim at. Declaring NO PATCH is the profile result for this
grade: procedure is beyond the authored-readout boundary for
this model (consistent with Phase 15's family-1 dates result
and with R3 existing precisely to test a second family here).
