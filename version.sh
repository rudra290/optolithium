#!/usr/bin/env bash
# ==============================================================================
# Optolithium Version Manager CLI Shortcut
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/tools/version_manager.py" "$@"

