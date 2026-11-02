#!/bin/bash
# Install the Jacquard ZCode adapter as a ZCode plugin from a
# local marketplace built out of this repository.
#
#   adapters/zcode/install_plugin.sh [marketplace-dir]
#
# Default marketplace dir: ~/jacquard-zcode-marketplace.
# The script copies adapters/zcode/plugin/ into the marketplace
# dir, writes the absolute path of adapters/zcode_hook.py into
# the plugin copy (ZCode installs plugins by copying them into
# its own cache, so the hook's location cannot be relative),
# registers the marketplace, and installs + enables the plugin.
#
# Remove with: adapters/zcode/uninstall_plugin.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MARKET="${1:-$HOME/jacquard-zcode-marketplace}"
PLUGIN_SRC="$REPO_ROOT/adapters/zcode/plugin"
ADAPTER="$REPO_ROOT/adapters/zcode_hook.py"

mkdir -p "$MARKET/jacquard-zcode"
cp -r "$PLUGIN_SRC/." "$MARKET/jacquard-zcode/"
printf '%s\n' "$ADAPTER" > "$MARKET/jacquard-zcode/hooks/adapter-path.txt"
cat > "$MARKET/marketplace.json" <<EOF
{"name": "jacquard-local", "plugins": [{"name": "jacquard-zcode", "source": "filesystem", "version": "0.1.0", "description": "Jacquard supervision for ZCode tool calls", "cachePath": "$MARKET/jacquard-zcode"}]}
EOF

zcode plugins marketplace add "$MARKET" --yes || true
zcode plugins install jacquard-zcode@jacquard-local --yes
zcode plugins enable jacquard-zcode@jacquard-local || true
echo "installed: jacquard-zcode@jacquard-local (adapter: $ADAPTER)"
