#!/bin/bash
# Install the Jacquard MCode adapter as a local MCode plugin.
#
#   adapters/mcode/install_plugin.sh [plugins-dir]
#
# Default plugins dir: ~/.minimax/plugins. MCode discovers
# local plugins by scanning that directory (a package is a
# directory whose .minimax-plugin/plugin.json it can load);
# there is no marketplace step for local packages, and
# `mcode plugin list -m local` shows what the scan found.
# The script copies adapters/mcode/plugin/ into
# <plugins-dir>/jacquard-mcode/ and writes the absolute path
# of adapters/mcode_hook.py into the installed copy's
# hooks/adapter-path.txt (MCode executes hooks from a
# content-hash cache copy of the package, so the hook's
# location cannot be relative).
#
# Remove with: adapters/mcode/uninstall_plugin.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLUGINS_DIR="${1:-$HOME/.minimax/plugins}"
PLUGIN_SRC="$REPO_ROOT/adapters/mcode/plugin"
ADAPTER="$REPO_ROOT/adapters/mcode_hook.py"
DEST="$PLUGINS_DIR/jacquard-mcode"

mkdir -p "$DEST"
cp -r "$PLUGIN_SRC/." "$DEST/"
printf '%s\n' "$ADAPTER" > "$DEST/hooks/adapter-path.txt"
echo "installed: jacquard-mcode in $PLUGINS_DIR (adapter: $ADAPTER)"
echo "verify with: mcode plugin list -m local"
