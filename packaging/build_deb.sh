#!/usr/bin/env bash
# ==============================================================================
# Script to build self-contained zero-dependency .deb package for Optolithium
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_DIR/dist/deb"
DEFAULT_VENV="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"

USE_NUITKA=false
BUNDLE_VENV=true
FORCE_REBUILD=false
VERSION=""
RELEASE="1"
ARCH="amd64"

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --nuitka          Compile with Nuitka into a 100% standalone native binary (zero Python runtime dependency)
  --standalone      Build fully self-contained zero-dependency DEB (default)
  --slim            Build slim DEB without bundling Python venv (requires internet/user venv)
  --bundle-venv     Bundle Python virtual environment (same as --standalone)
  --rebuild         Force rebuilding C++ core engine and plugins before packaging
  --output-dir DIR  Specify output directory for .deb files (default: dist/deb)
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

if [ -z "$VERSION" ]; then
    VERSION="$(grep -E '__version__\s*=' "$REPO_DIR/OptolithiumGui/info.py" | head -n1 | cut -d'"' -f2)"
    if [ -z "$VERSION" ]; then
        VERSION="0.3.0"
    fi
fi

DEB_PKG_NAME="optolithium_${VERSION}-${RELEASE}_${ARCH}.deb"

echo "=========================================================="
echo " Building Optolithium DEB Package"
echo " Version:     $VERSION"
echo " Release:     $RELEASE"
echo " Arch:        $ARCH"
echo " Mode:        $([ "$BUNDLE_VENV" = true ] && echo "Standalone Zero-Dependency (Bundled Runtime)" || echo "Slim (Host / User Virtualenv)")"
echo " Output Dir:  $OUTPUT_DIR"
echo " Package:     $DEB_PKG_NAME"
echo "=========================================================="

# Check if C++ core and plugins need rebuilding
CORE_SO="$REPO_DIR/OptolithiumGui/_optolithiumc.so"
CLIPPER_SO="$REPO_DIR/OptolithiumGui/_clipper.so"

if [ "$FORCE_REBUILD" = true ] || [ ! -f "$CORE_SO" ] || [ ! -f "$CLIPPER_SO" ]; then
    echo "==> Rebuilding C++ core libraries and plugins..."
    bash "$REPO_DIR/rebuild_linux.sh"
fi

# Build staging on POSIX filesystem (/tmp)
TMP_BUILD_DIR="/tmp/optolithium-debbuild-$USER-$$"
STAGING="$TMP_BUILD_DIR/pkg"
mkdir -p "$STAGING"/DEBIAN
mkdir -p "$STAGING"/opt/optolithium/app
mkdir -p "$STAGING"/opt/optolithium/bin
mkdir -p "$STAGING"/opt/optolithium/lib
mkdir -p "$STAGING"/usr/bin
mkdir -p "$STAGING"/usr/share/applications
mkdir -p "$STAGING"/usr/share/icons/hicolor/128x128/apps
mkdir -p "$STAGING"/usr/share/pixmaps

echo "==> Staging application files..."
INSTALL_APP="$STAGING/opt/optolithium/app"
INSTALL_BIN="$STAGING/opt/optolithium/bin"
INSTALL_LIB="$STAGING/opt/optolithium/lib"

if [ "$USE_NUITKA" = true ]; then
    echo "==> Compiling Optolithium with Nuitka into standalone native distribution..."
    NUITKA_OUT="$TMP_BUILD_DIR/nuitka"
    bash "$REPO_DIR/packaging/build_nuitka.sh" --standalone --output-dir "$NUITKA_OUT"
    mkdir -p "$STAGING/opt/optolithium"
    cp -a "$NUITKA_OUT/optolithium.dist"/* "$STAGING/opt/optolithium/"
    ln -sf /opt/optolithium/optolithium "$STAGING/usr/bin/optolithium"
else
    # 1. Copy application files
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

    # 3. Launcher script
    cp -f "$REPO_DIR/packaging/optolithium-launcher.sh" "$INSTALL_BIN/optolithium"
    chmod 755 "$INSTALL_BIN/optolithium"

    # 4. /usr/bin symlink
    ln -sf /opt/optolithium/bin/optolithium "$STAGING/usr/bin/optolithium"
fi

# 5. Desktop entry
cp -f "$REPO_DIR/packaging/optolithium.desktop" "$STAGING/usr/share/applications/optolithium.desktop"
chmod 644 "$STAGING/usr/share/applications/optolithium.desktop"

# 6. Icons
ICON_SRC="$REPO_DIR/Logo.png"
if [ ! -f "$ICON_SRC" ]; then
    ICON_SRC="$REPO_DIR/OptolithiumGui/icons/Logo.png"
fi
cp -f "$ICON_SRC" "$STAGING/usr/share/icons/hicolor/128x128/apps/optolithium.png"
cp -f "$ICON_SRC" "$STAGING/usr/share/pixmaps/optolithium.png"
chmod 644 "$STAGING/usr/share/icons/hicolor/128x128/apps/optolithium.png" "$STAGING/usr/share/pixmaps/optolithium.png"

# 7. Bundle complete venv if requested (default: standalone)
if [ "$BUNDLE_VENV" = true ]; then
    echo "==> Bundling Python runtime environment for zero-dependency execution..."
    if [ ! -d "$DEFAULT_VENV" ]; then
        echo "Error: Virtual environment not found at $DEFAULT_VENV" >&2
        echo "Please run ./rebuild_linux.sh first to set up the environment." >&2
        rm -rf "$TMP_BUILD_DIR"
        exit 1
    fi
    mkdir -p "$STAGING/opt/optolithium/venv"
    rsync -a \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude="*.pyo" \
        --exclude="share/doc" \
        --exclude="share/man" \
        "$DEFAULT_VENV/" "$STAGING/opt/optolithium/venv/"

    # Ensure interpreter symlinks point to the versioned python binary (e.g. /usr/bin/python3.12)
    PY_VER_TAG=""
    for d in "$STAGING/opt/optolithium/venv"/lib/python3.*; do
        if [ -d "$d" ]; then
            PY_VER_TAG="$(basename "$d")"
            break
        fi
    done
    if [ -n "$PY_VER_TAG" ]; then
        ln -sf "/usr/bin/$PY_VER_TAG" "$STAGING/opt/optolithium/venv/bin/$PY_VER_TAG"
        ln -sf "$PY_VER_TAG" "$STAGING/opt/optolithium/venv/bin/python3"
        ln -sf "python3" "$STAGING/opt/optolithium/venv/bin/python"
    fi
fi

# Calculate installed size in KB
INSTALLED_SIZE="$(du -sk --exclude="./DEBIAN" "$STAGING" | cut -f1)"

# 8. Create Debian control file with proper dependencies
if [ "$USE_NUITKA" = true ]; then
    DEB_DEPS="libc6 (>= 2.31)"
else
    DEB_DEPS="libc6 (>= 2.31)"
fi

cat << EOF > "$STAGING/DEBIAN/control"
Package: optolithium
Version: ${VERSION}-${RELEASE}
Section: science
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Alexei Gladkikh <gladkikhalexei@gmail.com>
Depends: ${DEB_DEPS}
Homepage: https://bitbucket.org/gladkikhalexei/lithography
Description: Modern Optical Lithography Simulation Suite (Standalone Zero-Dependency)
 Optolithium is an optical lithography simulation and modeling software suite.
 It provides advanced physical optical simulations, partial coherent imaging,
 resist exposure, post-exposure bake (PEB), development rate models, and
 rigorous metrology analysis.
 This package is completely self-contained with all runtime dependencies bundled.
EOF

# 9. Post-installation scriptlet
cat << 'EOF' > "$STAGING/DEBIAN/postinst"
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q /usr/share/icons/hicolor || true
    fi
fi
exit 0
EOF
chmod 755 "$STAGING/DEBIAN/postinst"

# 10. Post-removal scriptlet
cat << 'EOF' > "$STAGING/DEBIAN/postrm"
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q /usr/share/icons/hicolor || true
    fi
fi
exit 0
EOF
chmod 755 "$STAGING/DEBIAN/postrm"

# 11. Generate md5sums
echo "==> Generating checksums..."
(cd "$STAGING" && find . -type f ! -path "./DEBIAN/*" -exec md5sum {} + | sed -e 's| \./| |' > DEBIAN/md5sums)
chmod 644 "$STAGING/DEBIAN/md5sums"

mkdir -p "$OUTPUT_DIR"
TARGET_DEB="$OUTPUT_DIR/$DEB_PKG_NAME"

# 12. Build .deb package
if command -v dpkg-deb >/dev/null 2>&1; then
    echo "==> Building package with dpkg-deb..."
    dpkg-deb --build --root-owner-group "$STAGING" "$TARGET_DEB"
else
    echo "==> 'dpkg-deb' not found; using standard portable ar/tar packager..."
    echo "2.0" > "$TMP_BUILD_DIR/debian-binary"
    (cd "$STAGING/DEBIAN" && tar --owner=0 --group=0 -czf "$TMP_BUILD_DIR/control.tar.gz" .)
    (cd "$STAGING" && tar --owner=0 --group=0 --exclude="./DEBIAN" -czf "$TMP_BUILD_DIR/data.tar.gz" .)
    (cd "$TMP_BUILD_DIR" && ar -rc "$TARGET_DEB" debian-binary control.tar.gz data.tar.gz)
fi

rm -rf "$TMP_BUILD_DIR"

echo "=========================================================="
echo " Standalone DEB Build Complete!"
echo " Package generated: $TARGET_DEB"
ls -lh "$TARGET_DEB"
echo "=========================================================="
echo "Zero-dependency installation on Ubuntu/Debian:"
echo "    sudo apt install $TARGET_DEB"
echo "=========================================================="
