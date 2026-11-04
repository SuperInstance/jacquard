# Captured fixtures — provenance

The `pretooluse-*.json` files are REAL MCode hook payloads,
captured 2026-11-04 on the Jetson AGX Thor from MCode 0.6.13
(MiniMax-M3.1-Flash) by a probe hook (a local MINIMAX-format
plugin whose hooks recorded stdin verbatim) during a live
`mcode exec` run in a scratch workspace. They are the payloads
MCode actually sent for read / write / bash tool calls,
unedited except for JSON pretty-printing. Transfer from the
Thor to this repo was hash-verified (sha256) per file.

Findings these captures ground (see
docs/slice39-mcode-live-fire.md): the payload is snake_case
only (hook_event_name, tool_name, tool_input, tool_use_id,
session_id, turn_id, transcript_path, cwd, model,
permission_mode); tool names are lowercase (`bash`, `read`,
`write`, `edit`, `glob`, `grep`, `fetch`, `web_search`);
`read`/`write` tool_input carries `path` (relative paths are
sent as-is); a PreToolUse `deny` in the Claude-style
hookSpecificOutput shape blocks the call before execution in
both `exec` and the interactive TUI; PostToolUse carries
`tool_response` with the execution result. No
`PostToolUseFailure` event exists in MCode's vocabulary.
