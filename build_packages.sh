#!/usr/bin/env bash
# ==============================================================================
# One-click script to build Optolithium RPM, DEB, and MSI packages
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BUILD_RPM=false
BUILD_DEB=false
BUILD_MSI=false
BUILD_NUITKA=false
NUITKA_ONEFILE=false
USER_SELECTED_TARGET=false
EXTRA_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --nuitka)
            BUILD_NUITKA=true
            EXTRA_ARGS+=("--nuitka")
            ;;
        --nuitka-only)
            BUILD_NUITKA=true
            BUILD_RPM=false
            BUILD_DEB=false
            BUILD_MSI=false
            USER_SELECTED_TARGET=true
            ;;
        --onefile)
            NUITKA_ONEFILE=true
            ;;
        --rpm)
            BUILD_RPM=true
            USER_SELECTED_TARGET=true
            ;;
        --deb)
            BUILD_DEB=true
            USER_SELECTED_TARGET=true
            ;;
        --msi)
            BUILD_MSI=true
            USER_SELECTED_TARGET=true
            ;;
        --all)
            BUILD_RPM=true
            BUILD_DEB=true
            BUILD_MSI=true
            USER_SELECTED_TARGET=true
            ;;
        --rpm-only)
            BUILD_RPM=true
            BUILD_DEB=false
            BUILD_MSI=false
            USER_SELECTED_TARGET=true
            ;;
        --deb-only)
            BUILD_RPM=false
            BUILD_DEB=true
            BUILD_MSI=false
            USER_SELECTED_TARGET=true
            ;;
        --msi-only)
            BUILD_RPM=false
            BUILD_DEB=false
            BUILD_MSI=true
            USER_SELECTED_TARGET=true
            ;;
        *)
            EXTRA_ARGS+=("$arg")
            ;;
    esac
done

# Default behavior: build Linux native packages (.rpm and .deb)
if [ "$USER_SELECTED_TARGET" = false ]; then
    BUILD_RPM=true
    BUILD_DEB=true
fi

if [ "$BUILD_RPM" = true ]; then
    echo "=========================================================="
    echo " Step: Building .rpm Package & DNF Repository"
    echo "=========================================================="
    "$SCRIPT_DIR/packaging/build_rpm.sh" "${EXTRA_ARGS[@]}"
    "$SCRIPT_DIR/packaging/create_dnf_repo.sh"
    echo ""
fi

if [ "$BUILD_DEB" = true ]; then
    echo "=========================================================="
    echo " Step: Building .deb Package & APT Repository"
    echo "=========================================================="
    "$SCRIPT_DIR/packaging/build_deb.sh" "${EXTRA_ARGS[@]}"
    "$SCRIPT_DIR/packaging/create_apt_repo.sh"
    echo ""
fi

if [ "$BUILD_MSI" = true ]; then
    echo "=========================================================="
    echo " Step: Preparing Windows .msi Package"
    echo "=========================================================="
    "$SCRIPT_DIR/packaging/build_msi.sh" "${EXTRA_ARGS[@]}"
    echo ""
fi

if [ "$BUILD_NUITKA" = true ]; then
    echo "=========================================================="
    echo " Step: Building Nuitka Standalone Binary"
    echo "=========================================================="
    NUITKA_FLAGS=()
    if [ "$NUITKA_ONEFILE" = true ]; then
        NUITKA_FLAGS+=(--onefile)
    else
        NUITKA_FLAGS+=(--standalone)
    fi
    "$SCRIPT_DIR/packaging/build_nuitka.sh" "${NUITKA_FLAGS[@]}"
    echo ""
fi

echo "=========================================================="
echo " Packaging Process Finished!"
echo "=========================================================="
if [ "$BUILD_NUITKA" = true ]; then
    echo "Nuitka Native Binaries:"
    ls -lh "$SCRIPT_DIR/dist/nuitka"/* 2>/dev/null || true
    echo ""
fi
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
    echo ""
fi
if [ "$BUILD_MSI" = true ]; then
    echo "MSI Packages & Staging:"
    ls -lh "$SCRIPT_DIR/dist/msi"/*.msi 2>/dev/null || true
    ls -d "$SCRIPT_DIR/dist/msi-staging" 2>/dev/null || true
fi
echo "=========================================================="
