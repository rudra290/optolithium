#!/usr/bin/env bash
# ==============================================================================
# Script to build .rpm package for Optolithium
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_FILE="$REPO_DIR/packaging/optolithium.spec"
OUTPUT_DIR="$REPO_DIR/dist/rpm"
DEFAULT_VENV="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"

BUNDLE_VENV=false
FORCE_REBUILD=false
VERSION=""
RELEASE="1"

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --slim            Build slim RPM without bundling Python venv (default)
  --bundle-venv     Bundle Python virtual environment for an all-in-one offline RPM
  --rebuild         Force rebuilding C++ core engine and plugins before packaging
  --output-dir DIR  Specify output directory for .rpm files (default: dist/rpm)
  --version VER     Set package version (default: from OptolithiumGui/info.py)
  --release REL     Set package release number (default: 1)
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slim)
            BUNDLE_VENV=false
            shift
            ;;
        --bundle-venv)
            BUNDLE_VENV=true
            shift
            ;;
        --rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --release)
            RELEASE="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            print_usage
            exit 1
            ;;
    esac
done

# Verify rpmbuild tool
if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "Error: 'rpmbuild' is required but not installed." >&2
    echo "Install it with: sudo dnf install -y rpm-build" >&2
    exit 1
fi

# Detect version if not provided
if [ -z "$VERSION" ]; then
    VERSION="$(grep -E '__version__\s*=' "$REPO_DIR/OptolithiumGui/info.py" | head -n1 | cut -d'"' -f2)"
    if [ -z "$VERSION" ]; then
        VERSION="0.3.0"
    fi
fi

echo "=========================================================="
echo " Building Optolithium RPM Package"
echo " Version:     $VERSION"
echo " Release:     $RELEASE"
echo " Mode:        $([ "$BUNDLE_VENV" = true ] && echo "Bundled Virtualenv (Offline Ready)" || echo "Slim (Host / User Virtualenv)")"
echo " Output Dir:  $OUTPUT_DIR"
echo "=========================================================="

# Check if C++ core and plugins need rebuilding
CORE_SO="$REPO_DIR/OptolithiumGui/_optolithiumc.so"
CLIPPER_SO="$REPO_DIR/OptolithiumGui/_clipper.so"

if [ "$FORCE_REBUILD" = true ] || [ ! -f "$CORE_SO" ] || [ ! -f "$CLIPPER_SO" ]; then
    echo "==> Rebuilding C++ core libraries and plugins..."
    bash "$REPO_DIR/rebuild_linux.sh"
fi

# RPM Topdir must be on a POSIX filesystem (since project might be on exfat)
RPM_TMP_DIR="/tmp/optolithium-rpmbuild-$USER-$$"
mkdir -p "$RPM_TMP_DIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
STAGING="$RPM_TMP_DIR/staging"

echo "==> Staging files into $STAGING..."
INSTALL_OPT="$STAGING/opt/optolithium"
INSTALL_APP="$INSTALL_OPT/app"
INSTALL_BIN="$INSTALL_OPT/bin"

mkdir -p "$INSTALL_APP" "$INSTALL_BIN"
mkdir -p "$STAGING/usr/bin"
mkdir -p "$STAGING/usr/share/applications"
mkdir -p "$STAGING/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$STAGING/usr/share/pixmaps"

# 1. Copy application files (excluding Windows binaries, temporary caches, and logs)
rsync -a \
    --exclude="*.dll" \
    --exclude="*.exe" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="logs" \
    --exclude="icons_sources" \
    --exclude=".vscode" \
    --exclude=".venv" \
    "$REPO_DIR/OptolithiumGui/" "$INSTALL_APP/"

# 2. Copy launcher script
cp -f "$REPO_DIR/packaging/optolithium-launcher.sh" "$INSTALL_BIN/optolithium"
chmod +x "$INSTALL_BIN/optolithium"

# 3. Create wrapper symlink in /usr/bin
ln -sf /opt/optolithium/bin/optolithium "$STAGING/usr/bin/optolithium"

# 4. Desktop entry
cp -f "$REPO_DIR/packaging/optolithium.desktop" "$STAGING/usr/share/applications/optolithium.desktop"

# 5. Icons
ICON_SRC="$REPO_DIR/Logo.png"
if [ ! -f "$ICON_SRC" ]; then
    ICON_SRC="$REPO_DIR/OptolithiumGui/icons/Logo.png"
fi
cp -f "$ICON_SRC" "$STAGING/usr/share/icons/hicolor/128x128/apps/optolithium.png"
cp -f "$ICON_SRC" "$STAGING/usr/share/pixmaps/optolithium.png"

# 6. Bundle venv if requested
if [ "$BUNDLE_VENV" = true ]; then
    echo "==> Bundling Python virtual environment into package..."
    if [ ! -d "$DEFAULT_VENV" ]; then
        echo "Error: Virtual environment not found at $DEFAULT_VENV" >&2
        echo "Please run ./rebuild_linux.sh first to set up the environment." >&2
        rm -rf "$RPM_TMP_DIR"
        exit 1
    fi
    mkdir -p "$INSTALL_OPT/venv"
    rsync -a --exclude="__pycache__" "$DEFAULT_VENV/" "$INSTALL_OPT/venv/"
fi

echo "==> Running rpmbuild..."
rpmbuild \
    --define "_topdir $RPM_TMP_DIR" \
    --define "_tmppath /tmp" \
    --define "pkg_version $VERSION" \
    --define "pkg_release $RELEASE" \
    --define "staged_root $STAGING" \
    -bb "$SPEC_FILE"

mkdir -p "$OUTPUT_DIR"
find "$RPM_TMP_DIR/RPMS" -name "*.rpm" -exec cp -f {} "$OUTPUT_DIR/" \;

echo "==> Cleaning up temporary build root..."
rm -rf "$RPM_TMP_DIR"

echo "=========================================================="
echo " RPM Build Complete!"
echo " Package(s) generated in: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.rpm
echo "=========================================================="
echo "You can install this package with DNF:"
echo "    sudo dnf install $(ls -1 "$OUTPUT_DIR"/*.rpm | head -n1)"
echo "=========================================================="

