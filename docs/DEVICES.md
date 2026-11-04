# Support & compatibility — what runs where

Platform notes for the profiles in `docs/QUICKSTART.md`:
what runs on each class of machine, its requirements, and
its platform limitations. Support states are summarised
here from production deployments; the deployment evidence
behind every statement is the device matrix,
`docs/slice30-device-matrix.md`, and the per-deployment
records it links. Where a device fact was measured, the
measured value is given.

| Platform | Profile | State |
|---|---|---|
| Linux server (x86_64) | Shared schedule; service host | In production |
| Jetson AGX Thor (aarch64) | GPU job-queue governance (bridge) | In production — no resident process, by design |
| WSL2 workstation (x86_64) | Coding-agent seat supervision | In production |
| Jetson Orin Nano Super (aarch64) | Coding-agent seat supervision | In production, with the tegra limitation below |
| Laptop (single-user) | Solo automations | Prepared — not yet deployed |

## The Oracle (server / coordination point)

- Profile: the shared schedule (`tools/jqbook.py`) and the
  home of the gpu deployment's log (kept here, not on the
  GPU box, so the record survives the bench).
- The board inbox is a git clone with an `origin` remote;
  applied bookings are commits pushed to it. jqbook
  preflights this and refuses a plain copy before deciding
  anything, before any kernel write.
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
  mcode 0.6.12, Claude Code also present. Full suite at its
  deployment measurement: **332 passed, 7 skipped**
  (counts are platform- and version-dependent; see the
  Orin note).
- GPU: NVIDIA GeForce RTX 4050; `nvidia-smi` is **not on
  PATH** in this WSL — it lives at
  `/usr/lib/wsl/lib/nvidia-smi`.
- Reachability: the box is reached through its reverse
  tunnels (Oracle slot 2222, or the Thor hub at
  192.168.0.78:2206). `Connection refused` on **both**,
  with the other boxes' slots listening, means the box or
  its WSL is down — a desk state, not a credential or
  client error. The box has been observed dark for a full
  booked working window in exactly this signature; no
  remote action can wake it.
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
Thor (0.6.13). **The MCode adapter is live** (Phase 14,
slice 39): `adapters/mcode_hook.py` plus the local plugin
in `adapters/mcode/`, live-fired and deployed on the Thor's
0.6.13 seat - hooks fire in `exec` and TUI modes, a
PreToolUse deny blocks before execution, and a governed
end-to-end run is recorded in
`docs/slice39-mcode-live-fire.md` (7 proposals, 6 hash-bound
approvals, 3 consumed executions, counted from the log).
The Orin's 0.6.12 seat was not live-fired: its MiniMax
sign-in had lapsed (`anonymous` / "Login required"); the
0.6.12 bundles ship the same hook grammar by static
inventory, so the adapter is expected to hold there once
the seat is signed in again - an expectation, not a
measurement.

What the surface actually is (all live-verified on 0.6.13):

- **Plugins are the only hook surface.** The runtime config
  schema has no `hooks` key (a config carrying one is
  silently ignored), a workspace `.claude/settings.json`
  is ignored, and a package at a workspace root is not
  loaded. Local plugins are directories under
  `~/.minimax/plugins/` scanned at runtime; verify with
  `mcode plugin list -m local` (the default list shows the
  official marketplace only).
- A MINIMAX manifest is strict and fails silently:
  `schemaVersion: 1`, a semver version, an existing
  `icon`, a `category` from the host's list, and `hooks`
  declared as an array of hooks-file paths (no default
  `hooks/hooks.json` lookup - that default is Claude/Codex
  format only, and Claude-format packages also work).
  Handlers take a `command` string (no `args` for MINIMAX)
  and a `timeout` in seconds, capped at 10.
- Payloads are snake_case; tool names are lowercase
  (`bash`, `read`, `write`, `edit`, `glob`, `grep`,
  `fetch`, `web_search`). There is no PostToolUseFailure
  event. PermissionRequest did not fire in headless runs
  (the smart policy auto-decides; `ask` needs TUI/ACP), so
  the adapter governs at PreToolUse, which fires under
  every permission policy.
- **The hook host fails open**: a hook that crashes,
  prints garbage, or exceeds its timeout lets the tool
  call proceed. The adapter fails closed on its own
  errors; the host-level fail-open is a platform
  limitation, watched via the latency sidecar.
- `mcode plugin marketplace list` hangs on a network
  refresh; local work never needs it.

## The laptop (HP) — pending

Not yet deployed, and not yet reachable by the fleet: no
tunnel slot answers for it, its mDNS names do not resolve
from the fleet, and joining is a desk action (power on,
join the LAN, cross-authorise the fleet key or take
tunnel slot 2226). The single-user profile in
the QUICKSTART is prepared for it; this cell fills when
the box joins and a deployment record can be counted from
its log — not before.
