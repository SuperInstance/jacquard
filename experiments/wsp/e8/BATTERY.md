# E8 battery — the custom decision model

Curated by `curate.py` from Jacquard's own record (inventory: `../E8-SOURCES.md`). Every number in this file is computed from the assembled JSONL files at curation time. The battery builder does not patch any model; the scorer is `score_decision.py`; the independent checks are `verify_e8.py`.

## The instrument

One item = one recorded governance decision: a compact canonical context (producer, effect shape/verb, resource or target, queue/policy state, stated facts) rendered only from facts available at decision time, plus the recorded outcome as gold (ALLOW / HOLD / DENY). For kernel logs the item is the proposal's FIRST decision entry (allow / queued / deny at submission); later release/reject entries for the same proposal are the queue's downstream, not separate items. For the booking board the recorded outcome is the incumbent's: the board took every row, so board gold is ALLOW throughout, and the shadow trial's contention computation is carried in the context as queue state, not as gold.

Two scores (see `score_decision.py`): (a) agreement-with-operator, gold = the recorded outcome; (b) agreement-with-correctness, on the subset where `operator_correct` is known, gold = `correct_outcome`. Learning the operator's mistakes as faithfully as their judgement is a finding, not a success. The custom model remains a sense behind the provider seam; it advises, it never decides.

## Sources and counts

| source | items |
|---|---:|
| board-shadow | 81 |
| gpu-windows | 17 |
| jev | 11 |
| proof-run | 9 |
| proof-run-2 | 36 |
| slice30-booking | 12 |
| **total** | **166** |

Source notes (all counts above are the assembled items, after the exclusions stated here):

- `board-shadow` — the agent-inbox booking board (`~/agent-inbox/schedule/*.md`, git history), replayed with the shadow-trial method (`tools/shadow_trial.py`): every booking row's first appearance is one proposal; rows that are retroactive notes (planned cell DONE at first appearance) and rows with unparseable start or duration are excluded, exactly as in the trial. The trial window (commits through 2026-11-02) reproduces the published trial's decided set; later rows are the same instrument run over the board's continuation. Rows first committed after the trial's 63 scanned commits but before the split boundary are diagnostic items whose correctness is unclassified (null), not trial items.
- `jev` — `tools/jev_experiment.py` cases(6): six real-dispatch cases rendered from `tests/data/gpu-queue/events.jsonl`, two reconstructed fixtures (labelled as such in the context), three policy/1 cases from the spec. The raw gpu-queue event stream itself is not turned into items (see Weaknesses).
- `proof-run` / `proof-run-2` — the frozen kernel logs `docs/proof-run/kernel.jsonl` and `docs/proof-run-2/kernel.jsonl`, one item per distinct proposal (first decision).
- `gpu-windows` — `docs/slice25/kernel.jsonl`, the slice-22 live log continued through window 2 (same log, seq 0-196). The slice-22 copy of the same log is NOT read separately. Job names and command shapes come from the log's `gpu-policy` senses and the bridge journal.
- `slice30-booking` — `docs/slice30/booking-log.jsonl`. Booking-class proposals whose board row also appears as a `board-shadow` item are dropped as contradictory-label duplicates of the same underlying booking (kernel gold HOLD vs board gold ALLOW): 5 dropped. Matching is seat-exact or by (normalised box, start): the slice-30 log calls the Orin 'orin' where the board file is jetson-orin.md, and records the governed seat where the board row records the occupied seat. The kept items are the operator config proposals (authority writes and board-import writes) — a distinct decision type from the board's own acceptance of any row they import.
- `docs/slice27` shadow rows re-price gpu-window submissions; they are used only as correctness evidence, never as separate items.

## The time split

**Boundary: 2026-11-03T00:00:00Z.** Items with a recorded-at timestamp before the boundary are diagnostic; at or after it, held-out. No item appears in both splits (checked by `verify_e8.py`), and the split is by time only — no shuffling. Diagnostic range: 2026-10-27T18:13:34+00:00 to 2026-11-02T23:54:43+00:00. Held-out range: 2026-11-03T01:14:48+00:00 to 2026-11-04T02:42:48+00:00.

Timestamp basis per source: board items carry the git commit timestamp of the row's first appearance; jev real-dispatch items carry the dispatch event's timestamp; kernel logs carry sequence numbers, not clocks, so proof-run, gpu-window and slice-30 items carry an era timestamp at source-window granularity (the window's dated report), flagged per item in `ts_basis`. The boundary never cuts inside a kernel-log source, so era assignment cannot move an item across the split; within-source order is the log sequence, preserved in the source pointer.

## Class balance

| split | n | balance |
|---|---:|---|
| diagnostic | 112 | ALLOW 72 / HOLD 37 / DENY 3 |
| heldout | 54 | ALLOW 47 / HOLD 2 / DENY 5 |

Per-source counts per split:

Diagnostic:

| source | n |
|---|---:|
| board-shadow | 56 |
| jev | 11 |
| proof-run | 9 |
| proof-run-2 | 36 |

Held-out:

| source | n |
|---|---:|
| board-shadow | 25 |
| gpu-windows | 17 |
| slice30-booking | 12 |

## Incumbent-wrong cases (operator_correct: false)

4 items. On these, the recorded outcome is the operator/incumbent's mistake; the correctness score (b) grades against `correct_outcome`, not against gold.

- `e8-board-shadow-018` (split diagnostic, source board-shadow) — gold ALLOW, correct HOLD. Evidence: shadow-trial report, disagreements item 2 (Incumbent wrong): a whole-box claim over a live exclusive seat, no declared exception in the row; the shadow would have queued it.
- `e8-board-shadow-025` (split diagnostic, source board-shadow) — gold ALLOW, correct HOLD. Evidence: shadow-trial report, disagreements item 4 (Incumbent wrong): the 23:00 whole-box booking ran into the live 02:00 whole-box booking; the fleet had to re-plan wrapup — the conflict was real and cost a shuffle.
- `e8-board-shadow-033` (split diagnostic, source board-shadow) — gold ALLOW, correct HOLD. Evidence: shadow-trial report, disagreements item 6 (Incumbent wrong): light read-only measurement over-booked the exclusive box seat at the same moment as wrapup's box booking; the double-claim on an exclusive seat is the board's error.
- `e8-gpu-windows-007` (split heldout, source gpu-windows) — gold DENY, correct ALLOW. Evidence: docs/slice22-live-report.md, 'Disagreements': Jacquard wrong: 1 — the first sentinel submission was denied as a feeder shape because its command's prose note mentioned gpuq and the feeder and the bridge regex matched; the shape was tightened and the resubmitted sentinel was allowed and dispatched (the ALLOW item for jacquard-sentinel later in this same source).

## Correctness coverage

`operator_correct` is null on 46 of 166 items (diagnostic 7, held-out 39), so score (b) is computed on 105 diagnostic and 15 held-out items. Null means the record genuinely does not settle correctness: the shadow trial's policy-gap disagreements (a concept is missing, not an error), board rows committed after the 2026-11-02 trial (no audit of later board decisions exists), the two contested slice-27 consumption repricings (raw v2 would hold; the refined policy exempts or no GPU time was at stake), and operator config writes (no classification record). Each null item carries its reason in `correctness_evidence`.

## Leakage scan

Contexts were scanned for outcome-lexicon tokens (allow/allowed, hold/held, deny/denied, queue/queued, release/reject/approve forms and refused/refusal). The scan rule and the hard-fail verdict-phrase patterns live in `verify_e8.py`; this section reports the soft hits it must surface, not hide. Token counts across all contexts: denied x1, held x1, queue x30, queued x1, refused x1.

Borderline naming case, flagged plainly: `e8-gpu-windows-005` carries the job name 'jacquard-held-1' — a name the window designers gave the job they designed to be held. The name is a decision-time fact in the record, but it is outcome-suggestive; a coordinator may drop this item rather than let a name teach the answer.

Known legitimate sources of those tokens: the resource name 'gpu job-queue' / 'job-queue' and queue-state descriptions (the queue is the resource being governed, a neutral mention); stated policy rules in the jev policy cases (e.g. 'Suspended producers are denied by policy' — the rule is a decision-time fact, present in the source text the experiment itself used); booking task text written by lanes at booking time. No context contains its item's outcome as a verdict statement; `verify_e8.py` fails the battery if a verdict-phrase pattern appears.

## Known weaknesses

- **DENY is rare in the diagnostic split** (ALLOW 72 / HOLD 37 / DENY 3). The record's denials cluster in the gpu windows (held-out). A patcher can learn ALLOW and HOLD shapes from the diagnostic split but sees very few denied shapes; held-out DENY performance will rest on a handful of items.
- **HOLD is rare in the held-out split** (ALLOW 47 / HOLD 2 / DENY 5): the later record is dominated by board acceptances and operator config writes. Held-out accuracy mostly measures ALLOW fidelity plus the gpu windows' DENY/HOLD minority.
- **Board gold is structurally uniform.** Every board item's recorded outcome is ALLOW (the incumbent took them all), so the board source alone teaches 'always allow bookings'. The signal that distinguishes the wrong acceptances is the contention state in the context, and it is graded by score (b), not score (a).
- **Policy facts make many kernel items rule-derivable.** Stating policy/1's protected effects (or gpu-bridge-policy/1's shapes) in the context means a model that reads the policy can derive most first decisions. That is the nature of the recorded decisions — the jev cases have the same property — and it is why the correctness split and the contention items carry the experiment's weight.
- **Standing-rule state is summarised, not reconstructed.** The context states whether a standing rule was in force for the shape (from the decision entry's `decided_by`); the rule's own history is not rendered. Two proof-run-2 shapes are near-identical across sessions with different outcomes, distinguished in the context only by that field.
- **Contexts the record does not preserve.** Fast-path read decisions and most gpu-window allow decisions carry no request detail in their decision entries; their contexts are rendered from class, effects, job name (journal / gpu-policy senses) and declared uses where the log records them, and say so where it does not. File contents of writes are never rendered (targets and byte counts only).
- **The raw gpu-queue stream is excluded.** tests/data/gpu-queue records ~1,637 dispatches, all incumbent-allowed, with no per-item Jacquard decision; turning them into items would flood the battery with uniform ALLOW filler. Only the jev experiment's curated rendering of its first six dispatches is included.
- **Era timestamps.** Kernel-log items are placed by their source window's dated report, not by a per-item clock (the logs have none). The time split is exact at source granularity and at commit/event granularity for board and jev items; it is not a per-second ordering inside a kernel log.
- **Fixture/policy jev cases are not fleet decisions.** Two are labelled reconstructed fixtures and three are spec policy cases; they are part of the repo's recorded experiment, kept because E8-SOURCES lists the experiment as a source, and flagged in each item's evidence.

## Noise band (held-out)

Held-out n = 54. A single accuracy figure on this split carries a Wilson 95% half-width of about +/-8.7 points around the shadow-trial baseline rate of 88%, and +/-12.9 points at 50%. Differences smaller than that are inside the noise band and must not be reported as effects. The held-out correctness subset is smaller still (n = 15 known-correctness items; Wilson half-width at 50% about +/-22.6 points) — score (b) on held-out data can detect only gross disagreement with correctness, not fine weighting differences.

