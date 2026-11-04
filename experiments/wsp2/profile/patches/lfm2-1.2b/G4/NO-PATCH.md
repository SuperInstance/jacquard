# LFM2-1.2B — G4 (procedure) — NO PATCH declared

Chained diagnostic (after G2 patch): **5.83%**. Probe
evidence (diagnostic split, chained model): the gold
answer's first token is the answer-position argmax on
**7/120** items and in the top-5 on 29/120 (weeks_days
11/21 is the only category with partial signal). Failures
are procedure computations (arith_chain answered '459' for
639), format-name substitutions no row bias can convert
(add_days_month answered 'February' where the gold is the
month NUMBER), and chain interference ('Yes' emitted on
numeric questions — the G1/G2 attractor, recorded in
PATCHING-RECORD). Date and chain arithmetic are not
present at the readout; NO PATCH, as for Qwen3-0.6B.
