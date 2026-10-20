#!/usr/bin/env bash
# ==============================================================================
# One-click script to build Optolithium RPM package and DNF repository
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Step 1: Building .rpm Package ==="
"$SCRIPT_DIR/packaging/build_rpm.sh" "$@"

echo ""
echo "=== Step 2: Creating DNF Repository and .repo Configuration ==="
"$SCRIPT_DIR/packaging/create_dnf_repo.sh"

echo ""
echo "=== All packaging artifacts created successfully in dist/ ==="
ls -lh "$SCRIPT_DIR/dist/rpm"/*.rpm
ls -lh "$SCRIPT_DIR/dist"/*.repo

