# Phase 17 W1 — blind grading results (coordinator-computed)

Grader: a separate role, blind throughout (never opened
scores.jsonl or W1-SHADOW.md). Sample: 66 items, stratified,
all panic alarmed/stampede specialist calls force-included.
Grader mix — mc: model 26 / code 20 / mixed 20; panic:
calm 42 / alarmed 24 / stampede 0. 23 items carry ambiguity
notes (in blind_labels.jsonl, committed verbatim from the
graders delivery — its push was credential-blocked, the file
arrived in its report and is byte-identical to its local
commit 6439a9e).

## Model/code dial — the battery number did not survive

| | agreement with grader | code recall | mixed recall | model recall |
|---|---|---|---|---|
| incumbent | 20/66 = 30.3% | 19/20 | 0/20 | 1/26 |
| specialist | 18/66 = 27.3% | 15/20 | 3/20 | 0/26 |

Battery held-out was 84.2% (mixed 75%). Live: specialist
27.3%, BELOW the incumbent it was grown to replace, with the
model class dead (0/26; the specialist predicted model zero
times in the sample, once in the whole corpus). Pre-stated
SURVIVES-CONTACT bar (>=74.2% and no dead battery-alive
class): FAIL, by 47 points and one dead class.
RE-COACHING TRIGGER (criteria): FIRED (-56.9 pts vs battery).

Mechanism, from the record: the battery was short messages;
live traffic is long documents (median 7,048 chars). On long
documents both readers saturate toward code (incumbent
predicted code 63/66, specialist 55/66) while the grader,
reading centre of gravity, finds model/mixed substance in
46/66. The coached readout was fitted to a distribution the
wild does not send.

## Panic dial — the letter of the bar, not the baseline

| | agreement with grader | calm recall | alarmed recall | stampede |
|---|---|---|---|---|
| incumbent | 42/66 = 63.6% | 42/42 | 0/24 | never predicted |
| specialist | 39/66 = 59.1% | 32/42 | 7/24 | 3 calls, 0 correct |

Pre-stated bar (>=40.8% agreement; no battery-alive class at
recall 0): agreement PASSES; alarmed is alive (7/24);
stampede recall is UNDEFINED — the grader found no stampede
in the sample, so the class half is untestable, and the
specialists 3 stampede calls were all wrong (2 grader-calm,
1 grader-alarmed; precision 0/3). Against the majority
baseline (always-calm = 63.6%) the specialist is BELOW the
incumbent on raw agreement: it buys the only alarmed vision
in the system (7 of 24 real alarms, precision 7/11 = 64%)
at the cost of 10 calm items misread. Whether that trade is
worth making is a serving decision, not a measurement.
Re-coaching trigger: NOT fired (59.1% live vs 50.8% battery
— the calm-heavy wild mix flatters agreement).

Grader colour worth keeping: the two nearest-stampede items
(c0035, c0039 — compounding failures across a night) were
logged by their authors in a routine tone and graded
alarmed with stampede ambiguity notes. This fleets traffic
understates its own alarm; any dial reading tone will
systematically under-read it.
