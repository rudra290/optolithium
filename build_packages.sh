#!/usr/bin/env bash
# ==============================================================================
# One-click script to build Optolithium RPM & DEB packages and repositories
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BUILD_RPM=true
BUILD_DEB=true
EXTRA_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --rpm-only)
            BUILD_RPM=true
            BUILD_DEB=false
            ;;
        --deb-only)
            BUILD_RPM=false
            BUILD_DEB=true
            ;;
        *)
            EXTRA_ARGS+=("$arg")
            ;;
    esac
done

if [ "$BUILD_RPM" = true ]; then
    echo "=========================================================="
    echo " Step 1: Building .rpm Package & DNF Repository"
    echo "=========================================================="
    "$SCRIPT_DIR/packaging/build_rpm.sh" "${EXTRA_ARGS[@]}"
    "$SCRIPT_DIR/packaging/create_dnf_repo.sh"
    echo ""
fi

if [ "$BUILD_DEB" = true ]; then
    echo "=========================================================="
    echo " Step 2: Building .deb Package & APT Repository"
    echo "=========================================================="
    "$SCRIPT_DIR/packaging/build_deb.sh" "${EXTRA_ARGS[@]}"
    "$SCRIPT_DIR/packaging/create_apt_repo.sh"
    echo ""
fi

echo "=========================================================="
echo " All Requested Packaging Artifacts Created in dist/ !"
echo "=========================================================="
if [ "$BUILD_RPM" = true ]; then
    echo "RPM Packages:"
    ls -lh "$SCRIPT_DIR/dist/rpm"/*.rpm 2>/dev/null || true
    echo "DNF Repo Config:"
    ls -lh "$SCRIPT_DIR/dist"/*.repo 2>/dev/null || true
    echo ""
fi
if [ "$BUILD_DEB" = true ]; then
    echo "DEB Packages:"
    ls -lh "$SCRIPT_DIR/dist/deb"/*.deb 2>/dev/null || true
    echo "APT Repo Config:"
    ls -lh "$SCRIPT_DIR/dist"/*.list "$SCRIPT_DIR/dist"/*.sources 2>/dev/null || true
fi
echo "=========================================================="
