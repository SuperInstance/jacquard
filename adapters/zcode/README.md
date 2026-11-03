# The ZCode adapter (Phase 5, slice 12)

`adapters/zcode_hook.py` connects ZCode (the fleet's coding-agent
seat) to the Jacquard kernel. Every tool call ZCode is about to
make is translated into a proposal in the coding-agent profile
(`src/jacquard/coding_agent.py`) and decided by the kernel before
it runs:

| ZCode tool | Profile class | Kernel path |
|---|---|---|
| Read, Glob, Grep, LS | `agent-read` | allowed at once (fast path) |
| Write, Edit, ApplyPatch | `agent-write` | queued for the operator |
| Bash | `agent-shell` | queued for the operator |
| WebFetch, WebSearch | `agent-network` | queued for the operator |

Queueing is the profile's policy data, not adapter branches:
writes and shell commands carry a `notify` request beside their
real request (a policy/1 protected effect, the booking profile's
mechanism); network actions queue on their own `send` effect. An
active standing rule for a shape (the learner's pipeline) lets
that shape fast-path instead — the queue shrinks as approvals
compile into rules.

Tools outside the four classes (host bookkeeping: todo lists,
plan mode, questions) get no hook output at all: the host's own
permission flow governs them, and the pass is counted in the
latency sidecar. After an approved shell action runs, the
PostToolUse hook reports its outcome against the action machine
in the kernel log, so the log records what actually ran and the
operator CLI never re-executes it.

## The queue story (for the operator)

The hook runs inline, so a queued action blocks THAT tool call —
that is the host's shape, stated plainly. What Jacquard changes
is everything around the block:

- The hook returns a deny whose reason names the proposal id and
  its **binding hash**, and tells the agent the item is batched
  for an operator decision, to continue other work and retry the
  exact action later. Nothing times out into a rejection.
- Decide the whole batch in one pass with the operator CLI
  (from the Jacquard repo):
  `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl queue`
  then `... decide approve <id> --hash <binding>` (or `deny`).
  The approval is hash-bound: you approve the item you were
  shown, and a changed item fails approval untouched.
- When the agent retries the identical action, the hook finds
  the unconsumed release in the log, records the consumption
  (a sense entry, so replay shows it), and allows it — once.
  One approval authorises one execution. A denied action stays
  denied for that exact payload; a changed action is a new
  proposal.
- The kernel log replays the whole story:
  `python3 tools/jq.py --log <workspace>/.jacquard/kernel.jsonl replay <id>`.

Tools outside the four governed classes (host bookkeeping —
todo lists, plan mode, questions) get no hook output at all:
the host's own permission flow governs them, and the pass is
counted in the latency sidecar. Adapter errors fail closed
(deny) for everything the adapter does decide. On PostToolUse
the hook also reports a released shell action's outcome
against its kernel action machine, so the log records what
actually ran (identical repeated commands confirm
oldest-first — see `docs/slice12-live-run.md`).

The kernel log lives at `$JACQUARD_LOG`, defaulting to
`<workspace>/.jacquard/kernel.jsonl`. `$JACQUARD_PRODUCER`
overrides the producer name (default `zcode-agent`). Every hook
invocation appends one line to a latency sidecar
(`<log>.latency.jsonl`: timestamp, tool, verdict, decision_ms —
no tool arguments), which is slice 15's raw material.

## Install

Two registration surfaces are shipped. **On the build this was
developed against (zcode-app-cli 3.16.3-40), only the plugin
surface actually runs** — see the finding below. The plugin is
the verified route:

```
adapters/zcode/install_plugin.sh
```

That builds a local marketplace in `~/jacquard-zcode-marketplace`
from `adapters/zcode/plugin/`, writes the adapter's absolute path
into the plugin copy (ZCode installs plugins by copying them, so
the path cannot be relative), and installs + enables
`jacquard-zcode@jacquard-local` through ZCode's own plugin CLI.
No ZCode configuration or permission setting is edited by hand.

**Scope, plainly: the plugin install is machine-global, not
per-workspace.** The marketplace lives under your home and the
enablement lands in `~/.zcode/cli/setting.json`, so every zcode
session on the box loads the adapter (each workspace still gets
its own kernel log, via `JACQUARD_LOG` / the workspace cwd).
The script takes an optional argument — the marketplace
directory — if you want it kept inside a particular tree:
`adapters/zcode/install_plugin.sh <dir>`. A `Duplicate plugin
hooks file ignored: hooks/hooks.json` warning during install
is known and harmless: the plugin enables and its hooks fire.
Verified builds: zcode-app-cli 3.16.3-40 (ProArt WSL2) and
3.16.2-38 (Jetson Orin), both with zcode-runtime 0.17.0.

The documented surface — a workspace config snippet — is
`config.example.json` in this directory: copy it to a workspace's
`.zcode/config.json`, replace the hook path with your checkout's
absolute path, and grant the workspace hook trust ZCode requires
(the `zcode hooks trust` CLI is a **hidden subcommand** — it
does not appear in the `zcode --help` command list; it exists
on both verified builds: `zcode hooks trust review --workspace
<ws> --json`, then
`zcode hooks trust grant --workspace <ws> --all-current
--bundle-digest <digest from review>`; any later edit to the
config re-pends trust, by digest). Where configuration-file
hooks are enabled in ZCode, this snippet alone is the whole
install.

### Finding: configuration-file hooks did not run on 3.16.3-40

Recorded with evidence in `docs/BUILDERS-LOG.md` (slice 12).
Summary: the vendor's hook skill says config-file hooks have no
trust gate and run with `hooks.enabled: true`. Observed: a
workspace trust gate exists (the `zcode hooks trust` CLI), and
even after granting it, interactive sessions logged
`workspace_hook.feature_disabled` at session start and no
config-file hook — workspace or user scope, under every
combination of `hooks.enabled` in either global file — ever
fired. Plugin hooks fired in the same sessions with all global
configuration at defaults. The adapter therefore ships both
surfaces and the live evidence uses the plugin. If a later
ZCode build enables workspace hooks, the config snippet becomes
the lighter install and nothing else changes: both surfaces
invoke the same `zcode_hook.py`.

### Headless `-p` mode: works, with the retry recipe

What slice 12 recorded (2026-11-02): in headless `zcode -p`
mode the kernel side worked (the retry was allowed and the
consumption recorded), but the host then produced no
PostToolUse event and no observable execution effect, and the
agent reported itself still blocked. That observation stands
as the record of that run — in it, approvals landed after the
seat had stopped retrying.

What the later deployments observed (Phase 11, slices 30-31,
on both verified builds): headless sessions completed the
full arc repeatedly — queued Bash/Write calls executed on
identical retry after hash-bound approval, PostToolUse fired,
consumptions recorded — **when the approvals landed while the
seat was still in its retry window**. The operative recipe,
also in `docs/QUICKSTART.md`: put the retry rule in the
agent's prompt (a queued action is not a rejection; retry the
exact action), and operate the queue in short polling passes
so decisions land within the window. Interactive seats remain
the lower-variance surface; headless is proven, not
guaranteed — the host's hook lifecycle is the variable, and
the adapter's verdicts were correct in every observed mode.

## Remove

```
adapters/zcode/uninstall_plugin.sh
```

plus delete the workspace `.zcode/config.json` if you installed
the snippet, and `zcode hooks trust revoke --workspace <ws> --all`
if you granted trust. The host is restored exactly: the adapter
is additive, and ZCode's own permission settings were never
touched. Kernel logs under workspaces' `.jacquard/` directories
are yours to keep (they are the audit record) or delete.

## Redaction posture — read this

The kernel log records full proposal requests, which for this
adapter include Write/Edit content and Bash command strings
verbatim: that completeness is what makes every decision
replayable. Consequences, honestly stated:

- **Secrets an agent puts in a Bash command or a file write
  WILL land in the workspace's `.jacquard/kernel.jsonl`.**
  Slice 12 implements NO redaction. Treat kernel logs as
  sensitive files: keep them out of shared repos (the demo
  workspaces gitignore them), do not paste them into tickets.
- The latency sidecar is safe to share: it carries tool names,
  verdicts and timings only, never arguments.
- A redaction seam belongs to beachhead 2's product work
  (chain-head anchoring, PII/redaction); it is deliberately not
  improvised here, because a redacted log entry changes what
  replay can prove and that trade-off deserves its own design.
