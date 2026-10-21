#!/usr/bin/env bash
# ==============================================================================
# Script to build self-contained zero-dependency .rpm package for Optolithium
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_FILE="$REPO_DIR/packaging/optolithium.spec"
OUTPUT_DIR="$REPO_DIR/dist/rpm"
DEFAULT_VENV="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"

USE_NUITKA=false
BUNDLE_VENV=true
FORCE_REBUILD=false
VERSION=""
RELEASE="1"

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --nuitka          Compile with Nuitka into a 100% standalone native binary (zero Python runtime dependency)
  --standalone      Build fully self-contained zero-dependency RPM (default)
  --slim            Build slim RPM without bundling Python venv (requires internet/user venv)
  --bundle-venv     Bundle Python virtual environment (same as --standalone)
  --rebuild         Force rebuilding C++ core engine and plugins before packaging
  --output-dir DIR  Specify output directory for .rpm files (default: dist/rpm)
  --version VER     Set package version (default: from OptolithiumGui/info.py)
  --release REL     Set package release number (default: 1)
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --nuitka)
            USE_NUITKA=true
            BUNDLE_VENV=false
            shift
            ;;
        --standalone|--bundle-venv)
            BUNDLE_VENV=true
            shift
            ;;
        --slim)
            BUNDLE_VENV=false
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
echo " Mode:        $([ "$BUNDLE_VENV" = true ] && echo "Standalone Zero-Dependency (Bundled Runtime)" || echo "Slim (Host / User Virtualenv)")"
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
INSTALL_LIB="$INSTALL_OPT/lib"

mkdir -p "$INSTALL_APP" "$INSTALL_BIN" "$INSTALL_LIB"
mkdir -p "$STAGING/usr/bin"
mkdir -p "$STAGING/usr/share/applications"
mkdir -p "$STAGING/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$STAGING/usr/share/pixmaps"

if [ "$USE_NUITKA" = true ]; then
    echo "==> Compiling Optolithium with Nuitka into standalone native distribution..."
    NUITKA_OUT="$RPM_TMP_DIR/nuitka"
    bash "$REPO_DIR/packaging/build_nuitka.sh" --standalone --output-dir "$NUITKA_OUT"
    mkdir -p "$INSTALL_OPT"
    cp -a "$NUITKA_OUT/optolithium.dist"/* "$INSTALL_OPT/"
    ln -sf /opt/optolithium/optolithium "$STAGING/usr/bin/optolithium"
else
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

    # 2. Bundle native system libraries (e.g. libfftw3)
    for lib in /lib64/libfftw3.so* /usr/lib64/libfftw3.so*; do
        if [ -f "$lib" ]; then
            cp -a "$lib" "$INSTALL_LIB/" 2>/dev/null || true
        fi
    done

    # 3. Copy launcher script
    cp -f "$REPO_DIR/packaging/optolithium-launcher.sh" "$INSTALL_BIN/optolithium"
    chmod +x "$INSTALL_BIN/optolithium"

    # 4. Create wrapper symlink in /usr/bin
    ln -sf /opt/optolithium/bin/optolithium "$STAGING/usr/bin/optolithium"
fi

# 5. Desktop entry
cp -f "$REPO_DIR/packaging/optolithium.desktop" "$STAGING/usr/share/applications/optolithium.desktop"

# 6. Icons
ICON_SRC="$REPO_DIR/Logo.png"
if [ ! -f "$ICON_SRC" ]; then
    ICON_SRC="$REPO_DIR/OptolithiumGui/icons/Logo.png"
fi
cp -f "$ICON_SRC" "$STAGING/usr/share/icons/hicolor/128x128/apps/optolithium.png"
cp -f "$ICON_SRC" "$STAGING/usr/share/pixmaps/optolithium.png"

# 7. Bundle complete venv if requested (default: standalone)
if [ "$BUNDLE_VENV" = true ]; then
    echo "==> Bundling Python runtime environment for zero-dependency execution..."
    if [ ! -d "$DEFAULT_VENV" ]; then
        echo "Error: Virtual environment not found at $DEFAULT_VENV" >&2
        echo "Please run ./rebuild_linux.sh first to set up the environment." >&2
        rm -rf "$RPM_TMP_DIR"
        exit 1
    fi
    mkdir -p "$INSTALL_OPT/venv"
    rsync -a \
        --exclude="tests" \
        --exclude="test" \
        --exclude="testing" \
        --exclude="docs" \
        --exclude="doc" \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude="*.pyo" \
        --exclude="share/doc" \
        --exclude="share/man" \
        "$DEFAULT_VENV/" "$INSTALL_OPT/venv/"

    # Ensure interpreter symlinks point to the versioned python binary (e.g. /usr/bin/python3.12)
    # rather than generic /usr/bin/python3 which may be an ABI-incompatible version on user systems.
    PY_VER_TAG=""
    for d in "$INSTALL_OPT/venv"/lib/python3.*; do
        if [ -d "$d" ]; then
            PY_VER_TAG="$(basename "$d")"
            break
        fi
    done
    if [ -n "$PY_VER_TAG" ]; then
        ln -sf "/usr/bin/$PY_VER_TAG" "$INSTALL_OPT/venv/bin/$PY_VER_TAG"
        ln -sf "$PY_VER_TAG" "$INSTALL_OPT/venv/bin/python3"
        ln -sf "python3" "$INSTALL_OPT/venv/bin/python"
    fi
fi

echo "==> Running rpmbuild..."
EXTRA_RPM_ARGS=()
if [ "$USE_NUITKA" = true ]; then
    EXTRA_RPM_ARGS+=(--define "without_py_requires 1")
else
    EXTRA_RPM_ARGS+=(--define "py_version ${PY_VER_TAG:-python3.12}")
fi

QA_RPATHS=0x002f \
QA_SKIP_BUILD_ROOT=1 \
rpmbuild \
    --define "_topdir $RPM_TMP_DIR" \
    --define "_tmppath /tmp" \
    --define "pkg_version $VERSION" \
    --define "pkg_release $RELEASE" \
    --define "staged_root $STAGING" \
    "${EXTRA_RPM_ARGS[@]}" \
    -bb "$SPEC_FILE"

mkdir -p "$OUTPUT_DIR"
find "$RPM_TMP_DIR/RPMS" -name "*.rpm" -exec cp -f {} "$OUTPUT_DIR/" \;

echo "==> Cleaning up temporary build root..."
rm -rf "$RPM_TMP_DIR"

echo "=========================================================="
echo " Standalone RPM Build Complete!"
echo " Package(s) generated in: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.rpm
echo "=========================================================="
echo "Zero-dependency installation with DNF:"
echo "    sudo dnf install $(ls -1 "$OUTPUT_DIR"/*.rpm | head -n1)"
echo "=========================================================="
