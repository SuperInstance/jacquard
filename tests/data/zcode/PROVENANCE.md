# Captured fixtures — provenance

The `pretooluse-*.json` files are REAL ZCode hook payloads,
captured 2026-11-02 on the Oracle from zcode-app-cli
3.16.3-40 by a probe hook (a local plugin whose PreToolUse
hook recorded stdin verbatim) during a live interactive
session in a scratch workspace. They are the payloads ZCode
actually sent for Read / Write / Bash tool calls, unedited
except for JSON pretty-printing.

Findings these captures ground (see docs/BUILDERS-LOG.md,
slice 12): the payload carries both camelCase and snake_case
spellings of the same fields; a PreToolUse `allow` decision
pre-empts ZCode's native permission prompt entirely (no
PermissionRequest hook fired in the session); on this build,
configuration-file hooks (workspace and user scope) never
fired under any combination of trust grant and
`hooks.enabled`, while plugin hooks fired with all global
configuration at its defaults.
