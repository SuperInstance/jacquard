#!/bin/bash
# Remove the Jacquard ZCode adapter plugin and its local
# marketplace. After this runs (and the workspace config
# snippet, if you installed that instead, is deleted), ZCode
# is exactly as it was before the adapter: the adapter never
# touches ZCode's own configuration or permission settings.
#
#   adapters/zcode/uninstall_plugin.sh [marketplace-dir]
set -uo pipefail

MARKET="${1:-$HOME/jacquard-zcode-marketplace}"

zcode plugins disable jacquard-zcode@jacquard-local || true
zcode plugins uninstall jacquard-zcode@jacquard-local --yes || true
zcode plugins marketplace remove jacquard-local --yes || true
rm -rf "$MARKET"
echo "removed: jacquard-zcode@jacquard-local and $MARKET"
