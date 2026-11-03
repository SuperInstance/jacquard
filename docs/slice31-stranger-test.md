# Slice 31 — the stranger test

Cold zero-shot agents, given only the draft QUICKSTART and
the repo it points to, onboarded four device profiles and
governed real actions. Every friction point was classified
doc-defect or product-defect, the defects were fixed, and
the profiles with findings were re-run with fresh agents
against the fixed docs. Round 1 ran 2026-11-03 from the
19:45 UTC bookings; the draft under test was
`docs/QUICKSTART.md` at 68b7444.

## Round 1

### T1 — schedule profile (Oracle): COMPLETED, with friction

Init imported 4 live rows; the probe booking committed
active; complete marked it DONE on the scratch board.
Friction: the board's required layout (`schedule/` inside
a clone) was unstated — doc. **jqbook committed and pushed
to `origin` in the inbox, and `init` succeeded silently
against a plain non-git copy — the failure would have
surfaced mid-propose, after the kernel decided: doc defect
(the requirement) with a product face (no preflight).**
`--lane` absent from the example — doc. The result's
`asserted_rank 10 / effective_rank 0` for a new lane was
unexplained by any doc — doc. `complete` and `counts`
never mentioned in the profile — doc.

### T2 — seat profile (ProArt): BLOCKED BY THE ENVIRONMENT

The ProArt answered neither route for the entire booked
window (Thor hub 2206 refused; Oracle slot 2222 absent;
the other boxes' slots listened throughout). The box or
its WSL was down — a desk state no remote action cures.
The agent substituted nothing and falsified nothing; its
doc findings came from a local read of the docs: dead
references (`docs/DEVICES.md`, `docs/ONBOARDING.md`,
`starters/` — all slice-32 deliverables, absent at the
tested HEAD) — doc; the headless recipe (retry rule +
operator polling pattern) existed nowhere a stranger
would look — doc; "workspace" undefined — doc; the pytest
contradiction (below) — doc.

### T3 — seat profile (Orin): COMPLETED, and found the real defect

One governed session: 3 proposals (2 shell, 1 write) all
queued → hash-bound approval → executed; 58-entry log,
queue empty at close. Friction: missing referenced docs —
doc. Install scope mismatch (plugin install is
machine-global; QUICKSTART framed it per-workspace) —
doc. Duplicate-hooks warning unexplained — doc. Verified-
build skew (README cites 3.16.3-40; the Orin runs
3.16.2-38) with no guidance — doc. The adapter README's
headless "known limit" vs QUICKSTART's silence, while the
limit did not reproduce — doc tension, resolved by the
slices 30–31 evidence (see Fixes). Queue-operation timing
guidance absent (retry cadence is seconds; manual deciding
is racy) — doc.

**And the finding of the slice — a product defect in code
the coordinator itself had shipped the same day:** run as
the QUICKSTART's install check, the suite on the Orin
showed 6 failures. Five were `tests/test_booking_board.py`:
its fixtures hard-coded a check-by of 2026-11-03 19:00 UTC
against a wall-clock live-row filter, so the tests began
failing at 19:00 UTC — 45 minutes before the booking that
found them even started. (The sixth is the known tegra
bubblewrap failure.) The coordinator's "338 passed" claim
earlier that day was true only because it was measured
before 19:00. Fixed calendar fixtures are a time bomb;
these are now computed relative to now.

### T4 — GPU profile (Thor): COMPLETED in two stages, with friction

Stage 1: counts on the live log (197 entries), then a
`stranger-test` bench submission — **held**, exactly as
designed, for unknown-producer (proposal a3ee4e7c…).
Friction: the install check requires pytest, which the
doc's "nothing else" contradicts — doc (the same defect
T2 found from the other side). The slice-22 report gives
no literal `--cmd` for the bench shape; the agent excavated
it from the committed kernel log — doc. `--output`'s form
(path vs artifact id) unreconciled between QUICKSTART and
the live log — doc. How to obtain the working copy, and
jqgpu's sibling-journal expectation, unstated — doc.

The coordinator approved the held item as presented.
Stage 2: released hash-bound, dispatched (gpuq job-15),
completed exit 0, artefact verified on the Thor, log +
journal returned to the Oracle with sha256 equality (log
at 227 entries, counts 19/11/3/5/0/14/12/1). One governed
deviation, correctly taken and fully reported: gpuq's
successor rule stranded job-15 after the standing sentinel
(job-14) completed ahead of it — so the agent submitted
the established sentinel shape behind it
(`jacquard-sentinel-4`, allowed by standing policy,
dispatched as job-16), restoring the canonical end state
(a sentinel standing last). The coordinator's own stage-2
brief had described the sentinel's position imprecisely;
the agent diagnosed the truth from the queue's status file
and the slice-25 pattern. Friction: the successor rule
nowhere in the QUICKSTART's GPU path — doc (the biggest of
this profile); dispatch's re-listing unexplained — doc;
the Oracle file-transfer route undocumented — doc.

## Fixes (all shipped before the re-runs)

**Product (commit e18de9a):**
1. `tests/test_booking_board.py` rewritten on relative
   times; two preflight tests added. Full suite after the
   fix, at 21:24 UTC (2½ hours past the bomb): **340
   passed, 7 skipped**; the booking battery 8/8.
2. `jqbook` preflight (adapter `preflight_inbox`): every
   board-writing command now refuses a non-git or
   origin-less inbox loudly, **before any kernel write**,
   naming the requirement.

**Docs (commits 0c59ca7, 56593e8):** QUICKSTART — pytest
scoped to the suite; the green claim device-qualified
(bubblewrap/tegra named); workspace defined; install
scope (machine-global), verified builds, duplicate-hooks
note; the headless retry recipe + prompt-decision
guidance; the GPU working-copy/journal/sha discipline, a
literal bench command, the artifact-id output form, the
successor rule and the sentinel pattern, dispatch
re-listing explained; the schedule profile's git-clone /
origin requirement, `--lane`, rank/ceiling/effective-rank
explained, `complete` + `counts` shown. Adapter README —
install scope, hidden `hooks trust` subcommand, verified
builds; the headless known-limit rewritten to the observed
position (slice-12's run stands as its record; slices
30–31 executed the full arc headless on both builds when
approvals landed in the retry window). And the three dead
references now exist: `docs/ONBOARDING.md`,
`docs/DEVICES.md`, `starters/`.

## Re-runs (fresh agents, fixed docs, same cards)

**T1 re-run — COMPLETED, and caught one more real trap.**
Init/propose/complete all worked first-try against the
fixed docs (scratch log 64 entries; probe booking active
→ done; live board provably untouched). The remaining
major friction was in the *fix itself*: the new text said
the inbox "must be a real clone with an origin remote",
but the two literal ways to copy a board are both wrong —
a `cp -a` copy keeps the **live** origin (and passes the
preflight: a successful propose would have pushed the
probe booking onto the live fleet board), and a local
`git clone` points origin at the live repo, whose
checked-out branch refuses pushes mid-apply. The agent
built the correct scratch pattern itself (clone + bare
scratch remote + `set-url`). That recipe, a warning in
exactly those terms, and the preflight claim restated at
its true strength are now in the doc (commit ac3651c),
together with the round's minor items: init semantics,
propose's output anatomy, booking-id provenance, UTC
stated, default rank 10.

**T3 re-run — COMPLETED clean.** One governed session on
the Orin: 3 proposals queued → approved → executed,
**pytest outcome `8 passed in 3.15s`** — the time-bombed
battery, passing on the device that exposed it. Kernel
log 56 entries, sha256
105339588febe69d3374c12a33c0a0754cdc3e0b73a36041e398a5c94babae2b
(coordinator-verified on the box); summary.md as tasked.
The agent's one install-friction item was retracted by
the agent itself when its full install output arrived:
the script's output contained everything the docs
promised, warning included — the third time today an
interim rendering, not a source, was wrong; the record
keeps the retraction with the finding.

**T2 re-run — not attempted: the ProArt stayed dark.**
Probed again at 21:32 UTC (no Oracle slot 2222, no Thor
hub 2206/8788): the box remained down past both booked
windows. The seat profile's stranger verdict rests on
T3 (same profile, second device) plus slice 30's ProArt
deployment; the ProArt cell is recorded as
environment-blocked, not passed and not failed.

## Verdict

Four profiles attempted from the docs alone; three
completed their governed work in round 1, and the fourth
was stopped by a dark box, not by the project. The re-runs
completed clean (one after its own correction was folded
in). The test did its job in the strong sense: it
falsified something real — a test suite with an expiry
time, shipped the same morning — most of the rest was
documentation that had not yet been written or had drifted
from the deployments, and every fix is in the repo with a
re-run behind it.
