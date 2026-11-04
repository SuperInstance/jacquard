#!/bin/bash
# Remove the Jacquard MCode adapter plugin installed by
# adapters/mcode/install_plugin.sh.
#
#   adapters/mcode/uninstall_plugin.sh [plugins-dir]
#
# Default plugins dir: ~/.minimax/plugins. The adapter is
# additive: no MCode configuration or permission setting was
# edited, so deleting the package directory is the whole
# removal. Kernel logs under workspaces' .jacquard/
# directories are yours to keep (they are the audit record)
# or delete.
set -euo pipefail

PLUGINS_DIR="${1:-$HOME/.minimax/plugins}"
rm -rf "$PLUGINS_DIR/jacquard-mcode"
echo "removed: $PLUGINS_DIR/jacquard-mcode"
