# Slice 39 live-fire — MCode hooks, and the adapter they earned

Provenance: run 2026-11-04 (UTC) on the Jetson AGX Thor
against **MCode 0.6.13** (MiniMax-M3.1-Flash, managed OAuth
sign-in), driven two ways: `mcode exec` headless runs and the
interactive TUI in a dedicated tmux session (`p14-mcode`,
created for this slice and killed after; no other session
touched). A probe plugin (`jacquard-probe`, a local
MINIMAX-format package whose only job was to append every
hook payload verbatim to a marker file) provided the
evidence; the adapter deployment at the end used the real
adapter from this branch. Nothing below is reconstructed:
payload shapes, counts and hashes are copied from the probe
marker, the kernel log and its latency sidecar.

The Orin seat (MCode **0.6.12**) could not be live-fired:
its MiniMax sign-in had lapsed — `auth-state.json` reports
`"status": "anonymous"`, the TUI shows "Login required", and
`mcode exec` refuses with "Sign in to MiniMax to use Agent
features". Static inventory of the 0.6.12 bundles shows the
same hook grammar (same event vocabulary, same manifest
validator requirements, same parser), so the adapter is
expected to hold there, but that is an expectation, not a
measurement; re-firing 0.6.12 after a re-login is a named
residual. Version behaviour is therefore reported for
0.6.13 only.

## Surfaces tried

| surface | fired? | blocked? | evidence |
|---|---|---|---|
| Local plugin, MINIMAX format (`.minimax-plugin/plugin.json` + declared `hooks/hooks.json`) | **yes** — SessionStart, UserPromptSubmit, PreToolUse, PostToolUse | **yes** | marker payloads; sentinel files absent under deny in exec + TUI |
| Local plugin, Claude format (`.claude-plugin/plugin.json` + `hooks/hooks.json`, `command`+`args` handlers) | **yes** | **yes** | sentinel present under allow (marker 2 lines), absent under deny (marker 5) |
| Runtime config file (`mcode exec --config x.yaml` carrying a `hooks:` key) | no | — | marker never created; sentinel created unimpeded. The config schema's top-level key set (read from the shipped bundle) contains no `hooks` key |
| Workspace `.claude/settings.json` with hooks | no | — | same negative |
| Plugin package at the workspace root | no | — | same negative |
| PermissionRequest (probe registered, `--permission smart`) | **never fired** | — | smart auto-decided every call, including a file deletion; no PermissionRequest line in any marker. `exec --help` documents `ask` as requiring TUI/ACP |

## What the host sends

Payloads are snake_case only. A PreToolUse event (real
capture, `tests/data/mcode/pretooluse-bash.json`):

```json
{"tool_name": "bash",
 "tool_input": {"command": "cat fixture-reply.txt",
                "description": "Print fixture-reply.txt contents"},
 "tool_use_id": "call_148bda6004b14389b4f4e45f",
 "hook_event_name": "PreToolUse",
 "session_id": "mvs_94eb843701aa44fb9c0fc84f3944033c",
 "turn_id": "turn_mw1iybgx_mlo9js",
 "transcript_path": "/tmp/minimax-plugin-hooks/transcripts/....compatible.jsonl",
 "cwd": "/home/caseydigennaro/p14-s39/ws",
 "model": "MiniMax-M3.1-Flash",
 "permission_mode": "bypassPermissions"}
```

Tool names are lowercase: `bash`, `read`, `write`, `edit`,
`glob`, `grep`, `fetch`, `web_search` (plus host-bookkeeping
tools such as `task` and `tool_search`). `read`/`write`
inputs carry `path` (relative paths are sent as-is) and
`content` for writes; `bash` carries `command` +
`description`. PostToolUse adds `tool_response` (content +
execution details). There is **no PostToolUseFailure
event** in MCode's vocabulary (SessionStart, SessionEnd,
UserPromptSubmit, PreToolUse, PermissionRequest,
PostToolUse, SubagentStart, SubagentStop, Stop, PreCompact,
PostCompact); failures surface inside PostToolUse.

Hook processes run with `PLUGIN_ROOT` /
`MINIMAX_PLUGIN_ROOT` / `CLAUDE_PLUGIN_ROOT` /
`CODEX_PLUGIN_ROOT` set to a **content-hash cache copy** of
the package (`~/.minimax/v2/plugin-hook-cache/sha256-tree-v1-…`),
`PLUGIN_DATA` at `~/.minimax/v2/plugin-data/hooks/<name>`,
and `*_PROJECT_DIR` at the workspace.

## Block semantics, error semantics

- A PreToolUse verdict of
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": "…"}}`
  blocks the call before execution, under `--permission
  full` and in the TUI's "Full access" mode alike. In the
  exec deny run the agent retried bash/glob/read/write
  variants; every one was intercepted and the sentinel file
  was never created; the agent quoted the probe's deny
  reason verbatim in its report. PostToolUse does not fire
  for blocked calls.
- **The host fails open.** A hook that exits non-zero,
  prints unparseable output, or sleeps past its timeout
  lets the tool call proceed (sentinel created in all three
  probe modes; the bundle's own log line for this path is
  "Plugin hook command failed open"). Handler timeouts are
  declared in **seconds, capped at 10** (default 5), so a
  hook's decision budget is 10 s at most. The adapter's
  fail-closed posture therefore covers failures the hook
  process survives to report (it returns a deny on any
  internal error); a hard crash or a >10 s stall is a
  host-level fail-open, and the adapter README states this
  as a limitation rather than papering over it.

## Traps found (the ZCode precedent repeated, in new clothes)

1. **Dropping a package into `~/.minimax/plugins/` is not
   enough to make it load — and failure is silent.** The
   MINIMAX manifest validator rejects the whole package
   (no diagnostic surfaced in CLI output or runtime logs)
   unless `.minimax-plugin/plugin.json` declares
   `schemaVersion: 1`, a semver version, an `icon` path
   that exists in the package, a `category` from the
   host's fixed list, and `hooks` as an array of path
   strings. The first probe build missed icon/category/
   hooks and simply never existed as far as the runtime
   was concerned.
2. **No default hooks file for MINIMAX packages.** The
   Claude/Codex loader defaults to `hooks/hooks.json`; the
   MINIMAX loader reads only what the manifest declares.
3. **MINIMAX handlers take a `command` string only** — an
   `args` array is rejected as unsupported (Claude-format
   handlers accept `args`).
4. **`mcode plugin list` shows the official marketplace
   only**; local packages appear under
   `mcode plugin list -m local`. `mcode plugin add <name>
   -m local` answers "not found in the local marketplace"
   for a package that is in fact installed and enabled —
   local packages need no add step at all, only the scan.
   `mcode plugin marketplace list` hangs on a network
   refresh (>120 s, killed) and is not needed for local
   work.

## The deployment (adapter, governed end-to-end)

The adapter was installed on the Thor from this branch
(`adapters/mcode/install_plugin.sh`;
`mcode plugin list -m local` →
`jacquard-mcode@local, enabled: true`) and governed a real
task in a fresh workspace (`~/p14-s39/ws-gov`): read
`note.txt`, write `hello.py` printing its greeting, run it.
The agent was given the standard retry rule (a QUEUED deny
is batched, not rejected; retry the exact action). The
operator approved the batch with `tools/jq.py` in three
polling passes while the run proceeded.

Counted **from the kernel log and its latency sidecar**
(110 log entries; final queue empty; state hash
`19306f0e95704bd6ea248ce81935b95488578aeb3e61ef82370ad950c6a5c3c5`):

| measure | count |
|---|---|
| hook invocations (sidecar lines) | 21 |
| distinct proposals | 7 (1 read, 1 write, 5 bash) |
| fast-path allows (read) | 1 |
| queue verdicts (deny-to-queue, incl. identical retries) | 9 |
| operator approvals (hash-bound) | 6 |
| operator denials | 0 |
| approval consumptions (executions allowed by a release) | 3 (the write, 2 bash) |
| PostToolUse outcome reports (action machines confirmed) | 2 |
| silent passes (host bookkeeping: `tool_search` ×4, read/write PostToolUse ×2) | 6 |

The write queued four times before its release landed,
then executed on the identical retry; `jq replay` for it
ends "final proposal state: closed" (queued
protected-effect:notify → released-by-operator → execution
applied write, notify). Three approved bash proposals were
never retried identically before the run ended — the agent
had moved to variants — so their releases stand unconsumed
in the log, exactly as the one-shot semantics intend. The
agent's own closing summary reported the queue arc
accurately ("both the file write and the execution were
initially held in the Jacquard operator queue rather than
refused… the write landed on the fourth attempt").
`hello.py` exists, runs, and prints "Ahoy from Sitka
harbour". Decision latency: 0.05–3.4 ms per hook decision
in the sidecar — three orders of magnitude inside the
host's 10 s cap.

## Verdict

The surface holds: hooks fire, payloads are stable and
complete, and a PreToolUse deny blocks before execution in
headless and TUI modes alike. The MCode adapter is built
to the ZCode adapter's contract (same kernel, same profile,
same queue semantics, same one-shot hash-bound approvals)
and is deployed on the Thor seat. Its one structural
caveat — host fail-open on hook crash/timeout — is a
property of MCode, not of the adapter, and is documented
as a limitation in `adapters/mcode/README.md`,
`docs/DEVICES.md` and the README.
