# Devices — what differs per machine

Per-device notes for the profiles in `docs/QUICKSTART.md`,
from the deployments' own evidence (Phase 11, slice 30's
device matrix is the source record:
`docs/slice30-device-matrix.md`). Where a device fact was
measured, the measured value is given — fleet notes drift;
these pages record what the deployments found.

## The Oracle (server / coordination point)

- Profile: the shared schedule (`tools/jqbook.py`) and the
  home of the gpu deployment's log (kept here, not on the
  GPU box, so the record survives the bench).
- The board inbox is a git clone with an `origin` remote;
  applied bookings are commits pushed to it. jqbook
  preflights this and refuses a plain copy before deciding
  anything (slice-31 fix).
- Moving files to or from the Oracle: the fleet's access
  wrapper runs commands only; use `scp` with the same
  options (egress proxy, instance key, pinned known-hosts)
  when a stranger-flow needs a file transfer, and verify
  sha256 on both sides.

## The Thor (Jetson AGX Thor — GPU box; Casey's bench)

- Profile: the shared job queue (`tools/jqgpu.py`) over a
  per-dispatch SSH bridge. **No resident Jacquard process
  runs on this box, by design and by the owner's rule** —
  the Thor is Casey's own workbench; Jacquard's surface is
  the bridge calls and the gpuq state, nothing else.
- The queue's law that strands newcomers: a finite job runs
  only with another job queued **behind** it. The
  deployment keeps a declared sentinel standing last
  (`jacquard-sentinel-N`, currently job-16 in gpuq);
  dispatch a sentinel behind your job or it waits, with
  `no_successor_holds` showing in gpuq's status.
- Bench shape: torch in `~/ml/.venv`; job artefacts land
  in `~/jacquard-gpu-live/` on the box.
- Measured suite/conformance on this class of device:
  see the Orin — same tegra kernel family caveat for
  bubblewrap (below).

## The ProArt (WSL2 workstation — eileen)

- Profile: coding-agent seat supervision (ZCode adapter,
  plugin surface).
- Measured platform: WSL2 kernel
  6.18.54.1-microsoft-standard-WSL2, Python 3.14.4,
  node v24.21.0, zcode-app-cli 3.16.3-40 (runtime 0.17.0),
  mcode 0.6.12, Claude Code also present. Full suite here:
  **332 passed, 7 skipped**.
- GPU: NVIDIA GeForce RTX 4050; `nvidia-smi` is **not on
  PATH** in this WSL — it lives at
  `/usr/lib/wsl/lib/nvidia-smi`.
- Reachability: the box is reached through its reverse
  tunnels (Oracle slot 2222, or the Thor hub at
  192.168.0.78:2206). `Connection refused` on **both**,
  with the other boxes' slots listening, means the box or
  its WSL is down — a desk state, not a credential or
  client error. (During slice 31 the box was dark for a
  full booked window; no remote action can wake it.)
- Casey's own tmux sessions on this box are his: list at
  most, never enter or capture. Seat work runs detached in
  its own directory.

## The Orin (Jetson Orin Nano Super — the front room)

- Profile: coding-agent seat supervision (ZCode adapter,
  plugin surface), on the box Casey sits at.
- Measured platform: Linux 6.8.12-1021-tegra aarch64,
  Cortex-A78AE, Python 3.12.3, node v24.22.0,
  zcode-app-cli 3.16.2-38 (runtime 0.17.0), mcode 0.6.12.
- Non-interactive ssh shells on this box do not initialise
  nvm: prepend the seat paths before invoking seat CLIs —
  `export PATH=$HOME/.nvm/versions/node/v24.22.0/bin:$HOME/.minimax-code/bin:$PATH`.
- **Bubblewrap does not hold under the tegra kernel**: the
  executor's sandbox test
  (`test_bwrap_sandbox_isolates_the_filesystem`) fails
  here although `/usr/bin/bwrap` exists. Suite on this
  box: **1 failed (that test), 333 passed, 10 skipped**;
  TypeScript conformance **14 PASS, 0 SKIP, 0 FAIL**. The
  collected test count is platform-dependent (344 here vs
  339 on x86 WSL2).
- `zcode hooks trust …` exists on this build as a **hidden
  subcommand** (absent from `zcode --help`'s list); the
  config-file hook route remains untested here — the
  plugin route is the proven one.
- Other lanes work on this box (it is the fleet's shared
  front room): book the seat on the board, and never enter
  or capture a tmux session that isn't yours.

## MCode (MiniMax Code), all boxes

Installed on the ProArt (0.6.12), the Orin (0.6.12) and the
Thor (0.6.13). Static inventory found `plugin` subcommands,
an `exec` headless mode (`--permission smart|full|off`,
`--config`, `--output-format json`), and a hook event
vocabulary in the shipped bundles — SessionStart,
PreToolUse, PermissionRequest, PostToolUse — with a
Claude/Codex-format plugin loader (`hooks/hooks.json`).
**No MCode hook has been live-fired yet**: as of this
writing MCode is supervised by governing what it emits
(board rows, files, jobs), and a Jacquard adapter via its
plugin route is a feasible, unbuilt next step. TUI seats
are driven through tmux; seat sessions belong to their
lanes.

## The laptop (HP) — pending

Not yet meshed: no tunnel slot answers for it, its mDNS
names do not resolve from the fleet, and joining is a desk
action (power on, join the LAN, cross-authorise the fleet
key or take tunnel slot 2226). The single-user profile in
the QUICKSTART is prepared for it; this cell fills when
the box joins and a deployment record can be counted from
its log — not before.
