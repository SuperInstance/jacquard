# Slice 30 — the device matrix

Phase 11, slice 30: for each device in the fleet,
inventory what it actually does, pick the genuinely
useful governance target, and deploy the proven
machinery against real work. Every filled cell below
carries a deployment record whose counts are derived
from the deployment's own kernel log. Unfilled cells
are named, not padded.

## Thor — GPU job queue (standing deployment, audited)

The slice-22 deployment is intact and was re-verified
end to end. The feeder is OFF;
`jacquard-sentinel-3` (gpuq job-14) remains queued by
design — the standing successor behind every finite
job; gpuq all-time: 1,647 done / 1 failed; GPU idle at
audit. The live log (on the Oracle,
~/jacquard-gpu-live/kernel.jsonl) holds 197 entries,
chain valid: 17 submitted / 10 allowed / 2 held /
5 denied / 12 dispatched / 10 completed / 1 failed.
Bench artifacts (bench-1…6, held-1, net-1, sentinel,
sentinel-2) are present on the Thor. The Phase 10
consumption gate remains built, tested, and INACTIVE;
its shadow evidence stands as recorded there.

Seats on this box (inventory): zcode (nvm v22.23.4 and
v24.22.2 both present), mcode 0.6.13, kimi 2.3.2. The
watch stage (tmux muse/muse2) was down at audit; the
only live tmux session is Casey's own `agent-world`,
not entered. Seat work on the Thor is Casey's bench
work; per the charter no new governance surface was
opened here — the chartered surface is the gpuq bridge
and it is exactly as slices 22/29 left it.

One evident candidate named and NOT taken: the
download-governor's attempt ledgers sit on this box (its
service was inactive at audit). Governing the download
queue would be a second Thor surface, outside the
charter and against the bench rule; it is recorded as
an observation for Casey, not a deployment.

## Oracle — the schedule board itself (new deployment)

The fleet's coordination flow — who books which shared
box, seat, and GPU, and when — is real multi-lane work
that previously ran on intent alone. It now runs
through Jacquard.

**What shipped** (repo: `adapters/booking_board.py`,
`tools/jqbook.py`, `tests/test_booking_board.py`):
`jqbook` routes every board write through the booking
profile (booking machine + contention and authority
senses, spec §14) before applying it. Reads are the
board as it stands; each apply commits to the board's
git history and the commit hash is journalled back into
the kernel log as a `board-apply` sense value, so the
record and the board cross-reference. Imports of
pre-existing rows are recorded as what they are —
operator config writes asserting another lane's facts,
with provenance stated in a `board-import` entry.

**Deployment record** (log on the Oracle,
~/jacquard-p11-bookings/kernel.jsonl; a copy ships
beside this document): 207 entries at the time of
writing, chain valid. Init imported 7 live bookings as
7 contention units — gitpp's two Oracle seats (zcode +
mcode), rolling-perception's Orin zcode, and this
phase's four lane bookings — skipping 83 dead or DONE
rows. Seat vocabulary was normalised to the profile's
classified set (first token; `cpu` maps to `detached`),
with originals preserved in the log.

**The first governed contention was real.** This
phase's own Orin zcode booking (17:50–20:00 UTC)
contended with rolling-perception's live Orin zcode
booking at equal effective rank (5) — under the
interim tie disposition the challenger HELD (proposal
62ad96e53ea83d78…; the only queued item in the log).
Nothing was written to the board for it. When the
incumbent's seat was observed finished (its session
rollout closed 17:23 UTC; no process running), the
operator completed the imported record kernel-side
(imported rows are closed by the operator, never by
rewriting another lane's board row — a rule the
adapter battery now tests) and released the held
booking: contention cleared, the machine stepped to
active, and the row was applied to the board (commit
387e76a). Two further governed bookings were approved
and applied; the two Phase-31 seat bookings (ProArt,
Orin) were committed to the board by their owning lane
ahead of the governed run and imported; and two rows
the coordinator initially applied by hand during setup
— a process deviation, recorded in the builder's log —
were corrected on the board itself (commit e366fa9,
removing them before re-application through the gate).

Defects found and fixed with tests during deployment
(the battery grew from 2 to 6): a held booking's record
must be read from its queued proposal, not committed
state; the booking-id slug collided for same-lane,
same-box rows (gitpp's two seats became one unit) and
now includes the normalised seat; `apply_row` is
idempotent on its `(jq:<id>)` marker; init always
grants the coordinating lane its authority ceiling;
imported bookings close kernel-side only.

## ProArt — coding-seat supervision (new deployment)

Casey's `build` tmux session was listed, never entered;
all work ran in a new directory (~/jacquard-p11-seat/)
on a detached headless seat, per the booking.

The ZCode adapter was installed by its documented
plugin surface into the new workspace only, and the
seat did its real work under governance in one headless
run: the repo's full test suite in its clone, a set of
platform fact-gathering commands, and a Write of its
platform report — every call proposed, queued, and
released by hash-bound batch approval while the seat
retried identically.

Deployment record (evidence:
~/jacquard-p11/evidence/proart/ on the Oracle — kernel
log, latency sidecar, platform report):

- **Kernel log: 109 entries, sha256
  3f6423b132ad5e6b8dc7f518fb2e1ee137340e8b9d675ee0f34e6bd2db622ee9**,
  folding clean; queue empty at close.
- **6 distinct proposals**: 5 agent-shell + 1
  agent-write (no reads or network calls — the seat
  used Bash for everything); 6 queue + 6 allow
  decisions, 0 denies; 6 consumptions; 6 executions.
  On this run headless PostToolUse fired for every Bash
  call — approvals landed while the session was still
  actively retrying (an observation refining slice 12's
  anomaly note, not a refutation of it).
- **Latency sidecar: 36 rows** — 30 Bash + 6 Write hook
  calls; verdicts 24 queue-denies (the retries), 6
  allows, 6 passes; hook decision latency median
  1.19 ms.
- **Suite on this box: 332 passed, 7 skipped in
  12.70 s** — the v1.1.0 tree, from the governed run
  itself.
- **Platform, as measured on the box** (the fleet's
  standing notes carry older versions; these are the
  seat's own): WSL2 kernel
  6.18.54.1-microsoft-standard-WSL2; Python 3.14.4;
  node v24.21.0; zcode-app-cli 3.16.3-40
  (zcode-runtime 0.17.0); mcode 0.6.12; Claude Code
  2.1.317 also present; GPU NVIDIA GeForce RTX 4050
  (driver 615.71.08), reachable as
  /usr/lib/wsl/lib/nvidia-smi (not on PATH).

A note on evidence, because this programme's rule is
that the record outranks any summary: an interim
handoff rendering of this leg's result carried
aggregate numbers irreconcilable with the artifacts
(proposal counts exceeding the log's entry count). The
leg's final report reconciles with the artifacts
figure for figure — every number above was
independently re-derived by the coordinator from the
log, the sidecar and the run output, and matches. (The
leg also flagged, itself, one backgrounded queue-check
snapshot containing a proposal id that does not exist
in its log — phantom data in transit, recorded here so
nobody later "discovers" it in either direction.) One
coverage gap, stated plainly: the operator-deny path
was not exercised — the seat never proposed anything
out of scope.

**MCode on this box: a plugin hook surface exists
(static evidence).** The deep inventory contradicts the
first-pass probe: `mcode` ships `plugin` subcommands
and an `exec` headless mode (`--permission
smart|full|off`, `--config`, `--output-format json`),
and its shipped bundles define a hook event vocabulary
— SessionStart, PreToolUse, PermissionRequest,
PostToolUse, among others — with per-plugin
hook-document validation and a Claude/Codex-format
compatibility loader (`hooks/hooks.json`). A Jacquard
adapter via the MCode plugin route therefore looks
feasible, analogous to ZCode's plugin route. Caveat,
stated as the leg stated it: this is static evidence
from minified bundles; no MCode hook was live-fired in
this phase, so the surface is **evidenced, not yet
verified** — a named next step, not a deployed
capability.

## Orin — coding-seat supervision (new deployment)

Same target as the ProArt — this box is the fleet's
front room, and its zcode + mcode seats do real work
daily. Setup: clone + adapter plugin installed under
~/jacquard-p11-seat/ (the adapter's own installer wrote
its enablement into ~/.zcode/cli/setting.json — the
documented route); a smoke log folded clean before the
session; the incumbent rolling-perception lane's tmux
sessions were not touched, and this cell's session
waited on the tie release recorded in the Oracle
section.

The governed session (evidence:
~/jacquard-p11/evidence/orin/ on the Oracle — kernel
log, latency sidecar, platform report):

- **Kernel log: 117 entries** (sha256
  5717625e1c82457feb987f042221416ef8be4ce8bca24d588536ced637f68337),
  queue empty at close. Kinds: transition 78, decision
  14, execution 10, machine 7, sense 4, definition 4.
- **10 distinct proposals**: 3 agent-shell (the pytest
  run, the conformance run, the platform-facts
  command), 1 agent-write (the platform report), 6
  agent-read — 4 queued + 10 allow decisions, 0 denies;
  the operator approved the three shell calls and then
  the write, hash-bound, while the seat retried; all
  executed, all consumptions recorded.
- **Latency sidecar: 36 rows** (Bash 18, Read 12, Write
  6; verdicts deny 16 / allow 10 / pass 10).
- **Suite on this box: 1 failed, 333 passed, 10
  skipped** (34.16 s in the governed run; the
  coordinator's own re-run reproduced it exactly,
  32.25 s). The one failure is environmental and
  deployment-relevant:
  `test_bwrap_sandbox_isolates_the_filesystem` — the
  executor's bubblewrap sandbox does not hold under
  the Orin's tegra kernel. The collected count itself
  is platform-dependent (344 here vs 339 on the
  ProArt's x86 WSL2).
- **TypeScript conformance: 14 PASS, 0 SKIP, 0 FAIL**
  — including `vectors.anchor_registry`, the check the
  Phase 9 registry work added. (The repo README still
  says 13; that staleness is a doc defect, carried
  into slice 32's README rework.)
- **Platform**: Linux orin 6.8.12-1021-tegra aarch64,
  Cortex-A78AE; Python 3.12.3; node v24.22.0;
  zcode-app-cli 3.16.2-38 (zcode-runtime 0.17.0);
  mcode 0.6.12. The report file on disk byte-matches
  the write content recorded in the log.

Two honesty notes. First, the seat's own closing
summary *understates* its completion — it reports the
report write "still queued" and the file absent, from
a read taken before the operator's approval landed;
the log shows the approval (seq 103–104), the
execution (106), the seat's own read-back of the
written file (110–116), and the file is present. The
artifact outranks the summary, in this direction too.
Second, the process record: the leg agent operated
every approval and then was lost — with the
coordinator VM's restart (≈17:28 UTC, below) — before
reporting; the coordinator's duplicate session launch
afterwards had no observable effect (zero entries: the
log was already closed). And the tie release that
opened this cell (Oracle section) was executed at true
≈17:31 UTC — before the incumbent's 18:30 check-by —
on observed idleness: the incumbent's seat session had
ended (its rollout closed 17:23 UTC, no process
running). The coordinator's VM clock was running
≈ +40 minutes fast at the time, which is how the
release came to be mistimed in the coordinator's
working notes; the board itself, kept on the Oracle's
clock, was never affected. The judgement stands on the
observation, and is recorded as a judgement, not a
clock reading.

MCode surface probe (this box, direct, then corrected
by the ProArt leg's deeper dig): the first pass read a
truncated `mcode --help` and grepped too narrow a tree,
and concluded — wrongly — that no surface exists. The
full picture is the ProArt section's finding: plugin
subcommands, an exec headless mode, and a hook event
vocabulary in the shipped bundles (static evidence,
unverified live). ~/.minimax-code itself holds
installer state (bin/, releases/, an empty
.mcode-active/), and ~/.mcode-dynamic-workflows/ is a
local workflow service with a sqlite store — post-hoc
records, not a decision surface. The corrected
cross-box statement is in the closing section.

## Laptop (HP) — single-user profile, prepared; cell pending

Reachability, checked 2026-11-03 from the VM and the
Orin: no reverse-tunnel slot on the Oracle answers for
it (2222–2225 are ProArt / Kimi / Orin / Thor); mDNS
names for it do not resolve from the Orin; no service
advertisement on the LAN is attributable to it. The
fleet's own mesh notes carry the same open item since
2026-10-23. **The laptop is dark to the fleet, and
this cell is not filled.** Joining is a desk action
only Casey can take: power it on, join the LAN,
cross-authorise the fleet key (or assign tunnel slot
2226).

The profile is prepared so the join is the only
remaining step: single-user, no server — the kernel
log lives under the home directory; producers are the
machine's own automations and any seat Casey runs
there (the ZCode-adapter profile exactly as deployed
on the ProArt is the first real use); operator surface
is tools/jq.py locally (jqserve on loopback only if a
second local producer ever needs it — none does yet);
nothing inbound. When the box joins, slice 30's
acceptance for this cell is the same as every other:
a deployment record counted from its log.

## What the matrix says

Four cells deployed and verified from their logs
(Thor's standing deployment audited; Oracle, ProArt
and Orin new), one pending a desk action (laptop). Two
cross-cutting findings: the fleet's seats split by
VERIFIED decision surface — ZCode governs at tool-call
granularity today, on two boxes, from its plugin
hooks; MCode carries a plugin hook surface on static
evidence (hook events incl. PreToolUse and
PermissionRequest, a Claude/Codex-format loader) that
nobody has live-fired yet, so its adapter is a
feasible, unbuilt next step rather than a gap to route
around — and the tie disposition earned its keep on
its first real contention: the Orin seat changed hands
by the record, at the incumbent's pace, with no lane's
work disturbed.

A process note for the whole slice: the coordinator VM
restarted at ≈17:28 UTC mid-slice. The garbled interim
handoff on the ProArt leg and the loss of the Orin leg
agent both trace to it. All deployment work lived on
the fleet boxes and survived; every number in this
document was re-derived from artifacts afterwards,
which is why the restart cost a correction addendum
and some hours — not a single figure.
