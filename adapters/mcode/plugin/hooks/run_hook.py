#!/usr/bin/env python3
"""Plugin launcher for the Jacquard MCode adapter.

MCode copies an installed plugin into its hook cache, so this
launcher cannot find the adapter by relative path. It resolves
the real hook (adapters/mcode_hook.py in the Jacquard repo) from,
in order: the JACQUARD_ADAPTER environment variable, then the
adapter-path.txt file the install script writes next to this
file before installation. If neither resolves, it fails CLOSED
(deny, "adapter error: ...") rather than letting the tool call
through unsupervised.
"""
import json
import os
import subprocess
import sys


def adapter_path():
    candidate = os.environ.get("JACQUARD_ADAPTER")
    if candidate and os.path.isfile(candidate):
        return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    marker = os.path.join(here, "adapter-path.txt")
    try:
        with open(marker, encoding="utf-8") as fh:
            candidate = fh.read().strip()
        if candidate and os.path.isfile(candidate):
            return candidate
    except OSError:
        pass
    return None


def main():
    raw = sys.stdin.read()
    path = adapter_path()
    if path is None:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    "adapter error: Jacquard adapter not found "
                    "(set JACQUARD_ADAPTER or reinstall via "
                    "adapters/mcode/install_plugin.sh); "
                    "failing closed"}}) + "\n")
        return 0
    proc = subprocess.run([sys.executable, path], input=raw,
                          capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0 and not proc.stdout:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    "adapter error: hook process exited %d: %s"
                    % (proc.returncode, proc.stderr[-300:])}}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
