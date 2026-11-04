# EXPLANATION — Jacquard Phase 15, E5 stage 3 (T3: unit conversion)

## EVIDENCED NEGATIVE — no critical patch is shipped for T3

Student: Qwen/Qwen3-0.6B (bf16, tied embeddings, 28 layers, hidden 1024,
751,632,384 parameters). **Base for this stage is the stage-2 patched model**
(`model-in/` = stage 1 + stage 2 composed). Artefacts in this directory:
`patch.py` (the stage-2 applier, protocol-identical), `edits.json` (control
group ONLY — see §5), built model in `patched-stage3/`, authoring/probe
scripts `gen_edits.py`, `probe3.py`, `trial3.py`, `lookup2.py`. All scores
from the fixed instrument (`score.py`, greedy, 96-token cap, last-number
extraction). No training, no gradients, no optimiser anywhere: every
measurement is a forward pass, and every trial edit is an authored
mean-direction logit bias of the same form stages 1–2 shipped.

**Result: T3 diagnostic 47/60 = 78.3% before → 47/60 = 78.3% after
(control-only patch; raw outputs item-by-item identical to the base).**
T1 diagnostic 90.0% → 90.0%; T2 diagnostic 26.7% → 26.7% — stage 1 and
stage 2 results fully retained, because nothing that could move them was
shipped. Receipt: 16 edit records (8 control rows × 2 stored copies),
**16,144 scalars changed = 0.00215%** of parameters (bound: 751,632 = 0.1%).

The finding of this stage is that the residual T3 failures are **conversion-
factor decisions, not format failures**, and no authored logit-level edit I
could find reaches them. The evidence is in §1–§4.

---

## 1. Diagnosis — the 13 T3 diagnostic failures, classified from raw outputs

Base (= stage-2 model) T3 diagnostic: 47/60 = 78.3% (dozen_gross 4/10,
metric_length 7/10, metric_volume 7/10, metric_mass 9/10,
imperial_length 10/10, time_conv 10/10) — identical to the unpatched base
model's diagnostic, i.e. stages 1–2 neither helped nor hurt T3.

| Failure class | Count | Items | Description |
|---|---|---|---|
| Wrong compounded factor (one-step stop on a two-step conversion) | 4 | t3diag-031, 035 (gross→items: ×12 instead of ×144), 041 (tonnes→grams: ×10⁴ instead of ×10⁶), 059 (m³→millilitres: ×10³ instead of ×10⁶) | Model applies the *first* step's factor (gross→dozen 12, tonne→kg 1000, m³→litres 1000) and labels the intermediate result with the target unit. |
| Inverted direction | 3 | t3diag-020 (mm→cm: ×10 instead of ÷10), 034, 040 (gross→dozen: ÷12 instead of ×12) | Right factor magnitude, wrong operation direction. |
| Identity / no conversion applied | 3 | t3diag-019 (140 mm = "140 centimetres"), 036 (396 dozen = "396 gross"), 052 (37,000 ml = "37,000 liters") | Model restates the quantity with the target unit name and no factor at all. |
| Wrong factor magnitude | 1 | t3diag-018 (cm→mm: ×1000 instead of ×10 → 29,000) | Applies a neighbouring metric factor (m→mm's 1000) to cm→mm. |
| Arithmetic slip (procedure right) | 1 | t3diag-038 (17 × 12 = **192**; gold 204) | Factor and direction correct; the multiplication itself is wrong. |
| Format / truncation (surface) | 1 | t3diag-060 (litres→m³ via a LaTeX `$$…\text{…}$$` essay that runs into the cap) | The only format-class failure — and §4 shows a factor/direction error underneath it. |

**Headline: 11 of 13 failures (85%) are factor/direction errors** — the
model chooses the wrong conversion factor, the wrong direction, or no
factor. Exactly 1 is an arithmetic slip and 1 is (superficially) format.
This is the inverse of T1 (53% format) and one step beyond T2: in T2 a
template-suppression patch could still harvest truncation relief (+8.3);
here there is essentially no truncation to harvest.

## 2. Probes — the capability exists, but only in decomposed form

Three forward-pass probes on the stage-2 model (`probe3.py`):

- **Direct factor recall (self-authored questions).** Every *single-step*
  factor is recalled correctly: 1 gross = 12 dozen ✓, 1 dozen = 12 items ✓,
  1 cm = 10 mm ✓, 1 tonne = 1000 kg ✓, 1 m³ = 1000 litres ✓, 1 litre =
  1000 ml ✓. But the *compounded* factors are not known as facts:
  "How many items are in 1 gross?" → "1 gross = **18** items";
  "Convert 1 gross to items" → "1 gross = **12** items". Asked to convert
  1 tonne → grams and 1 m³ → millilitres directly, the model *does*
  decompose spontaneously at n=1 ("1 tonne = 1000 kilograms = 1,000,000
  grams") — at n=8 and n=6 it does not.
- **Continuation probe (teacher-forced correct decompositions, all 13
  failing items).** Given the correct decomposition on the page
  ("25 gross = 25 x 144 =", "8 tonnes = 8000 kilograms = 8000 x 1000 =",
  "260 millimetres = 260 / 10 =", …), the model completes **13/13
  correctly**, with the gold first digit on top by wide margins
  (e.g. '2' at 29.6 vs runner-up 22.4 for 23 × 12). The arithmetic
  primitives and the step factors are all present and strong.
- **Factor-position probe.** At the decision point of the gross→items
  failure ("25 gross = 25 × 1|"), the model prefers '2' (→ ×12, logit
  23.25) over '4' (→ ×144, logit 19.0) — a 4.25-logit *content* preference
  for the wrong factor, not a near-tie a bias could arbitrate without
  also flipping every other '2'-vs-'4' decision in the battery.

So the failure is precisely: **the model does not spontaneously produce
the two-step decomposition, and does not know the compounded factors.**
That is a procedure/knowledge gap of exactly the kind stage 2's §6
identified — one level deeper, because here even the surface templates
are short, completed, and confident.

## 3. Answer to the brief's question: can a logit-level patch address a wrong factor?

Measured answer: **no, not with the authored-bias instrument that worked
in stages 1–2.** A constant logit bias (mean-direction delta on a token
row) is context-light: it can arbitrate *which surface form* the model
reaches for (digit vs essay opener; sentence frame vs full stop), because
those competitions recur with the same shape at every occurrence. A factor
choice is the opposite kind of decision: ×12 vs ×144, × vs ÷, is correct
or wrong *depending on the unit pair in the prompt*, and the same tokens
('1', '2', '4', ' ×', ' dozen', ' litres') must win in some contexts and
lose in others. Every trial in §4 that pushed one of these tokens moved
surface wording while the factor decision stayed put, or traded correct
items for incorrect ones at exactly even rates. Making the model *generate
a decomposition it does not generate* — the only route by which its own
verified primitives would produce the right factor — is a capability
intervention, not a bias, and '1'-boosting (the one lever that did trigger
relation-first style) corrupts digit content through the tied input side
before it helps (§4), the same trap stage 1 documented at high digit-bias
strengths and stage 2 measured again.

## 4. Variants tried and rejected on evidence (in-memory trials, `trial3.py`)

All trials are mean-direction biases on the stage-2 model, scored on the
T3 diagnostic split (n=60, base 78.3%). None exceeded baseline; the
plateau is exact, not approximate — five different levers land on
precisely 47/60 with the identical miss set.

| Trial | T3 diag | What happened |
|---|---|---|
| '1' boost +5 (trigger relation-first style) | 75.0% | Relation-first *did* trigger and metric_volume rose 0.7→0.9, but the style loops ("1 tonne = 1000 kg" ×5, truncating) and the tied input-side shift corrupts prompt digits (21120 read as 12120): imperial 1.0→0.8, dozen 0.4→0.3, mass 0.9→0.8. |
| '1' boost +3 | 78.3% | Pure churn: fixes t3diag-038 (arithmetic) and 060 (truncation), breaks t3diag-026 and 030 (imperial, previously 10/10). |
| '1' boost +2 | 76.7% | Churn, net negative (breaks 026, 030, 032). |
| ' dozen' +6 (force the intermediate label after ×12) | 78.3% | Identical miss set; t3diag-036's surface changed, its answer got *worse* in content (396 × 12 = 4752 "gross"). The label follows the number decision, not vice versa. |
| ' litres' +6 | 78.3% | Identical miss set; t3diag-052 now spells the wrong identity answer with 'litres'; 060 reroutes, still wrong. |
| ' dozen' + ' litres' + ' kilograms' +6 combined | 78.3% | Identical miss set. |
| ' divided' −8 (against gross→dozen inversions) | 78.3% | Identical miss set — 040 reroutes to '÷', same division. |
| '÷' byte-token (1683) −8 | 78.3% | Identical miss set. |
| ' ×' −6 (destructive control) | 78.3% | Identical miss set — multiplication reroutes to other surface forms with the same factors. |
| digit '4' +5 (toward ×144 at the factor position) | 73.3% | Does not flip the gross items; corrupts unrelated digit decisions (imperial 0.8, mass 0.8). Confirms §2: the 4.25-logit factor gap is not a bias-sized near-tie in any useful sense — a global +5 on '4' costs more elsewhere than it buys there. |
| ' equal' −6 (against the identity-answer frame) | 76.7% | Identity answers reroute, still identity; metric_volume falls to 0.6. |
| '$$' −10 (against the t3diag-060 LaTeX essay) | 78.3% | 060 reroutes from truncation to a *completed* computation — "38000 × 1000 = 38,000,000 cubic metres": wrong direction. The stage's one format failure was a factor error wearing a format costume. |
| ' gross' −6 (against the t3diag-036 identity label) | 76.7% | Dozen falls to 0.3 (032 breaks); 036 unfixed. |

## 5. What is shipped, and the critical prediction

`edits.json` contains **only** the protocol control group: rows
151646–151653 (reserved special tokens this text-only model never emits
in these batteries) × both stored copies of the tied embedding, each
given the standard −8 mean-direction delta (m̂ measured on the 60 T3
diagnostic prompts of the stage-2 model: mean projection 134.7, range
123.0–144.9). There is **no critical set**, deliberately: shipping any of
the §4 levers as "critical" would assert an effect the diagnostic
evidence contradicts.

**Prediction (for E4 ablation).** The shipped patch is inert by
construction and by measurement: patched-stage3 reproduces the stage-2
model's scores exactly (T3 78.3%, T1 90.0%, T2 26.7%) with T3 raw outputs
identical item-by-item. Ablating the control set returns the base model
itself; ablating any equal count of (nonexistent) critical edits is
vacuous. If a future stage finds a real T3 lever, this stage's claim to
test is the negative one: *no single-token or few-token mean-direction
bias at strengths ≤10 logits raises T3 diagnostic above 78.3% without
breaking a previously-perfect category* — the §4 table is the evidence,
and a counterexample would contradict it cleanly.

## 6. What remains broken, and why

12 of the 13 failures are, at root, the model not knowing or not applying
the right conversion factor in context (the 13th, t3diag-038, is a plain
multiplication slip of the kind stage 1 already found not patch-
addressable). The chain's lesson compounds across stages: stage 1
harvested a format failure (+11.2 diagnostic), stage 2 harvested the
truncation relief inside a procedure failure (+8.3), and stage 3's target
is a **factor-knowledge failure with almost no format component at all** —
the authored-patch instrument's yield on it is measured zero. The
capability the model needs (spontaneous two-step decomposition; the
compounded facts 144, 10⁶) is demonstrably *in* the model in decomposed
form (§2), so this is a routing failure, not missing knowledge in the
deep sense — but routing a model to a procedure via constant logit biases
was tried from six directions and the procedure never appeared without
collateral damage exceeding the gain.

## 7. Predicted held-out effect

The shipped patch is control-only and output-identical to the stage-2
model on the diagnostic split. **Predicted T3 held-out effect: 0 points**
(the stage-2 model's T3 held-out level should reproduce exactly, up to
the harness's own nondeterminism; the ±7-point noise band at n=120 is
stated for completeness, but the prediction is exact inertness, not a
small positive). T1 and T2 held-out likewise unaffected. For the
*unshipped* levers, the diagnostic evidence predicts transfer of nothing:
every candidate was flat or negative on its own tuning split, so no
honest positive held-out prediction exists for any of them.
