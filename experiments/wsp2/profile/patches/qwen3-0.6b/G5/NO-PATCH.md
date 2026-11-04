# Qwen3-0.6B — G5 (factor-knowledge) — NO PATCH declared

Chained diagnostic (after G3 patch): **18.0%** (pristine base
16.0%). Failure taxonomy on the diagnostic split: of 82 wrong
items, **74 are bare, short, wrong answers** — not format
failures. Capitals 0/31 with outputs that echo the country
('Austria' for Vienna, 'Maldives' for Male) or fall into the
chain's 'Yes' attractor; solar 0/10, history_misc 0/10,
animal_misc 1/16. The exception is element_symbol (86.67%
chained), a closed symbol table the model demonstrably has.

An open fact set (100 distinct golds in the diagnostic split
alone) has no label rows and no per-fact readout geometry a
0.1%-dose row patch could install — authoring facts is
memorisation, not readout repair, and the probe shows the
gold answers are not ranked at the answer position (the
model's top answers are echoes and attractors). NO PATCH:
the knowledge is absent, which is what G5 exists to detect.
