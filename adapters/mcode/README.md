# The MCode adapter (Phase 14, slice 39)

`adapters/mcode_hook.py` connects MCode (MiniMax Code, the
fleet's second coding-agent seat) to the Jacquard kernel.
Every tool call MCode is about to make is translated into a
proposal in the coding-agent profile
(`src/jacquard/coding_agent.py`) and decided by the kernel
before it runs:

| MCode tool | Profile class | Kernel path |
|---|---|---|
| read, glob, grep | `agent-read` | allowed at once (fast path) |
| write, edit | `agent-write` | queued for the operator |
| bash | `agent-shell` | queued for the operator |
| fetch, web_search | `agent-network` | queued for the operator |

Queueing is the profile's policy data, not adapter branches:
writes and shell commands carry a `notify` request beside
their real request (a policy/1 protected effect, the booking
profile's mechanism); network actions queue on their own
`send` effect. An active standing rule for a shape (the
learner's pipeline) lets that shape fast-path instead — the
queue shrinks as approvals compile into rules.

Tools outside the four classes (host bookkeeping: `task`
sub-agents, questions, plan/todo tools) get no hook output at
all: the host's own permission flow governs them, and the
pass is counted in the latency sidecar. After an approved
shell action runs, the PostToolUse hook reports its outcome
against the action machine in the kernel log, so the log
records what actually ran and the operator CLI never
re-executes it. MCode has no PostToolUseFailure event; a
failed execution is reported from the PostToolUse payload's
own error flag.

## The queue story (for the operator)

The hook runs inline, so a queued action blocks THAT tool
call — that is the host's shape, stated plainly. What
Jacquard changes is everything around the block:

- The hook returns a deny whose reason names the proposal id
  and its **binding hash**, and tells the agent the item is
  batched for an operator decision, to continue other work
  and retry the exact action later. Nothing times out into
  a rejection.
- Decide the whole batch in one pass with the operator CLI
  (from the Jacquard repo):
  `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl queue`
  then `... decide approve <id> --hash <binding>` (or
  `deny`). The approval is hash-bound: you approve the item
  you were shown, and a changed item fails approval
  untouched.
- When the agent retries the identical action, the hook
  finds the unconsumed release in the log, records the
  consumption (a sense entry, so replay shows it), and
  allows it — once. One approval authorises one execution.
  A denied action stays denied for that exact payload; a
  changed action is a new proposal.
- The kernel log replays the whole story:
  `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl replay <id>`.

The kernel log lives at `$JACQUARD_LOG`, defaulting to
`<workspace>/.jacquard/kernel.jsonl`. `$JACQUARD_PRODUCER`
overrides the producer name (default `mcode-agent`). Every
hook invocation appends one line to a latency sidecar
(`<log>.latency.jsonl`: timestamp, tool, verdict,
decision_ms — no tool arguments).

## Install

One registration surface is shipped: a **local plugin** in
MCode's MINIMAX format. It is the only surface that runs —
see the findings below.

```
adapters/mcode/install_plugin.sh
```

That copies `adapters/mcode/plugin/` into
`~/.minimax/plugins/jacquard-mcode/` (the directory MCode
scans for local plugins) and writes the adapter's absolute
path into the installed copy's `hooks/adapter-path.txt`
(MCode executes hooks from a content-hash cache copy of the
package, so the path cannot be relative). No MCode
configuration or permission setting is edited by hand.
Verify with `mcode plugin list -m local` (the default
`mcode plugin list` shows the official marketplace only).
The install is machine-global, not per-workspace: every
mcode session on the box loads the adapter; each workspace
still gets its own kernel log, via `JACQUARD_LOG` / the
workspace cwd.

Verified build: MCode 0.6.13 (Jetson AGX Thor), live-fired
in both `mcode exec` headless mode and the interactive TUI
— see `docs/slice39-mcode-live-fire.md`. The 0.6.12 build
(Jetson Orin) ships the same hook grammar (verified by
static inventory of its bundles); its seat was not
live-fired in slice 39 because its MiniMax sign-in had
lapsed (the seat reported `anonymous` / "Login required").

### Findings: the surfaces that do not run (0.6.13, live-tested)

- **No configuration-file hooks exist.** The runtime config
  schema (`~/.minimax/config.yaml`, or a file passed with
  `mcode exec --config`) has a fixed top-level key set with
  no `hooks` key; a config file carrying one is silently
  ignored (probe hook never fired, tool calls unimpeded).
  A Claude-style workspace `.claude/settings.json` with
  hooks is likewise ignored, and a plugin package placed at
  a workspace root is not loaded. Plugins are the only hook
  surface.
- **A MINIMAX plugin manifest is strict.** The package is
  silently dropped from the local scan unless
  `.minimax-plugin/plugin.json` declares `schemaVersion: 1`,
  a semver `version`, an `icon` path that exists in the
  package, a `category` from the host's list, and `hooks`
  as an array of hooks-file paths (there is no default
  `hooks/hooks.json` lookup for MINIMAX packages — that
  default exists only for the Claude/Codex formats).
  Handlers take a single `command` string (an `args` array
  is rejected for MINIMAX format) and a `timeout` in
  **seconds, capped at 10** (default 5).
- **A Claude-format package also works** (`.claude-plugin/
  plugin.json` + `hooks/hooks.json` with `command` + `args`
  handlers): hooks fired and blocked identically in slice
  39's tests. The adapter ships the MINIMAX format because
  it is the host's native one.
- **PermissionRequest did not fire in headless runs.** In
  `mcode exec` under `--permission smart`, tool calls were
  auto-decided by the host's smart policy with no
  PermissionRequest event (even for a file deletion);
  `ask` is documented as requiring the TUI/ACP. The adapter
  therefore governs at PreToolUse, which fires under every
  permission policy including `--permission full`
  (payload `permission_mode: "bypassPermissions"`).

### The fail-open limitation — read this

MCode's plugin-hook host **fails open**: a hook process that
exits non-zero, prints unparseable output, or exceeds its
timeout is logged ("Plugin hook command failed open") and
the tool call proceeds unsupervised. Slice 39 verified all
three live. Consequences, stated plainly:

- The adapter itself fails closed — any adapter-internal
  error becomes a deny verdict, never an allow — but that
  covers only failures the hook process survives to report.
  A hard crash (interpreter missing, hook file unreadable)
  or a >10 s stall is a host-level fail-open.
- Kernel decisions are milliseconds, so the timeout is not
  a practical risk for this adapter; the residual risk is a
  broken installation. The install script's verification
  step (`mcode plugin list -m local`) and the latency
  sidecar (one line per governed call) are the detection
  surface: a seat whose sidecar stops growing while it works
  is a seat that has fallen out of governance.

## Remove

```
adapters/mcode/uninstall_plugin.sh
```

The host is restored exactly: the adapter is additive, and
MCode's own permission settings were never touched. Kernel
logs under workspaces' `.jacquard/` directories are yours
to keep (they are the audit record) or delete.

## Redaction posture — read this

The kernel log records full proposal requests, which for
this adapter include write/edit content and bash command
strings verbatim: that completeness is what makes every
decision replayable. Consequences, honestly stated:

- **Secrets an agent puts in a bash command or a file write
  WILL land in the workspace's `.jacquard/kernel.jsonl`.**
  Slice 39 implements NO redaction. Treat kernel logs as
  sensitive files: keep them out of shared repos (the demo
  workspaces gitignore them), do not paste them into
  tickets.
- The latency sidecar is safe to share: it carries tool
  names, verdicts and timings only, never arguments.
- A redaction seam belongs to beachhead 2's product work
  (chain-head anchoring, PII/redaction); it is deliberately
  not improvised here, because a redacted log entry changes
  what replay can prove and that trade-off deserves its own
  design.
