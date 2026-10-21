#!/usr/bin/env bash
# ==============================================================================
# Script to compile Optolithium into a 100% Standalone Native Linux Binary (Nuitka)
# Zero Python runtime dependencies: runs on any machine with or without Python.
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUI_DIR="$REPO_DIR/OptolithiumGui"
OUTPUT_DIR="$REPO_DIR/dist/nuitka"
DEFAULT_VENV="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"

MODE="standalone"   # "standalone" (directory) or "onefile" (single executable)
FORCE_REBUILD=false
JOBS="$(nproc 2>/dev/null || echo 4)"

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Compile Optolithium using Nuitka into a completely standalone, zero-dependency
native binary that requires NO Python installation on target machines.

Options:
  --standalone      Build standalone directory with bundled libraries (default, fastest startup)
  --onefile         Build a single standalone self-extracting executable binary
  --rebuild         Force rebuilding C++ core libraries and plugins before compilation
  --output-dir DIR  Specify output directory (default: dist/nuitka)
  --jobs N          Number of parallel compilation jobs (default: nproc)
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --standalone)
            MODE="standalone"
            shift
            ;;
        --onefile)
            MODE="onefile"
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
        --jobs)
            JOBS="$2"
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

echo "=========================================================="
echo " Optolithium Nuitka Native Compiler"
echo " Mode:        $MODE (Zero Python Runtime Dependency)"
echo " Output Dir:  $OUTPUT_DIR"
echo " Parallel:    $JOBS jobs"
echo "=========================================================="

# 1. Check C/C++ compiler and patchelf
if ! command -v gcc >/dev/null 2>&1; then
    echo "Error: 'gcc' is required for Nuitka compilation." >&2
    echo "Install it with: sudo dnf install -y gcc (or sudo apt install -y gcc)" >&2
    exit 1
fi

if ! command -v g++ >/dev/null 2>&1; then
    echo "Error: 'g++' (gcc-c++) is required for Nuitka compilation." >&2
    echo "Install it with: sudo dnf install -y gcc-c++ (or sudo apt install -y g++)" >&2
    exit 1
fi

if ! command -v patchelf >/dev/null 2>&1; then
    echo "Warning: 'patchelf' is recommended for standalone ELF binary patching." >&2
    echo "Install it with: sudo dnf install -y patchelf (or sudo apt install -y patchelf)" >&2
fi

# 2. Determine Python environment with Nuitka and dependencies
# OptolithiumC was built against libpython3.12.so.1.0; prefer python3.12 for ABI compatibility
PYTHON_BIN=""
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
elif [ -n "$OPTOLITHIUM_VENV" ] && [ -x "$OPTOLITHIUM_VENV/bin/python" ]; then
    PYTHON_BIN="$OPTOLITHIUM_VENV/bin/python"
elif [ -x "$DEFAULT_VENV/bin/python" ]; then
    PYTHON_BIN="$DEFAULT_VENV/bin/python"
elif [ -x "/opt/optolithium/venv/bin/python" ] && [ "$(/opt/optolithium/venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)" = "3.12" ]; then
    PYTHON_BIN="/opt/optolithium/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Error: No Python environment found to drive the Nuitka build." >&2
    exit 1
fi

echo "==> Using Build Python: $("$PYTHON_BIN" --version 2>&1) at $PYTHON_BIN"

# Check if libpython3.12.so.1.0 is available on system
if [ -f "$GUI_DIR/_optolithiumc.so" ]; then
    NEEDED_LIB="$(readelf -d "$GUI_DIR/_optolithiumc.so" 2>/dev/null | grep -o 'libpython3\.[0-9]\+\.so\.[0-9.]*' | head -n1 || true)"
    if [ -n "$NEEDED_LIB" ] && ! ldconfig -p 2>/dev/null | grep -q "$NEEDED_LIB" && [ ! -f "/lib64/$NEEDED_LIB" ] && [ ! -f "/usr/lib64/$NEEDED_LIB" ]; then
        echo "================================================================================" >&2
        echo "Error: OptolithiumC core simulation library requires $NEEDED_LIB" >&2
        echo "Please install Python 3.12 runtime and development headers on your system:" >&2
        echo "    sudo dnf install -y python3.12 python3.12-devel" >&2
        echo "================================================================================" >&2
        exit 1
    fi
fi

# Add bundled or user site-packages to PYTHONPATH if present
for sp in /opt/optolithium/venv/lib/python*/site-packages "$DEFAULT_VENV"/lib/python*/site-packages "$HOME/.local/lib/python3."*/site-packages; do
    if [ -d "$sp" ]; then
        export PYTHONPATH="$sp:${PYTHONPATH:-}"
    fi
done

# Locate Nuitka binary
NUITKA_CMD=()
if "$PYTHON_BIN" -m nuitka --version >/dev/null 2>&1; then
    NUITKA_CMD=("$PYTHON_BIN" -m nuitka)
elif command -v nuitka >/dev/null 2>&1; then
    NUITKA_CMD=(nuitka)
elif [ -x "$HOME/.local/bin/nuitka" ]; then
    NUITKA_CMD=("$HOME/.local/bin/nuitka")
else
    echo "==> Nuitka not found. Attempting to install..."
    if "$PYTHON_BIN" -m pip install nuitka 2>/dev/null || pip install nuitka 2>/dev/null; then
        NUITKA_CMD=("$PYTHON_BIN" -m nuitka)
    else
        echo "Error: Could not locate or install Nuitka." >&2
        echo "Please install Nuitka with: pip install nuitka" >&2
        exit 1
    fi
fi

# 3. Check C++ core libraries and plugins
CORE_SO="$GUI_DIR/_optolithiumc.so"
CLIPPER_SO="$GUI_DIR/_clipper.so"

if [ "$FORCE_REBUILD" = true ] || [ ! -f "$CORE_SO" ] || [ ! -f "$CLIPPER_SO" ]; then
    echo "==> Building C++ core simulation engine and plugins..."
    bash "$REPO_DIR/rebuild_linux.sh"
fi

# 4. Prepare build directory
BUILD_TMP="/tmp/optolithium-nuitka-build-$USER-$$"
mkdir -p "$BUILD_TMP"
mkdir -p "$OUTPUT_DIR"

echo "==> Compiling Optolithium with Nuitka ($MODE mode)..."

NUITKA_ARGS=(
    --jobs="$JOBS"
    --assume-yes-for-downloads
    --output-dir="$BUILD_TMP"
    --output-filename="optolithium"
    --enable-plugin=pyqt5
    --enable-plugin=numpy
    --enable-plugin=matplotlib
    --include-data-dir="$GUI_DIR/icons=icons"
    --include-data-dir="$GUI_DIR/plugins=plugins"
    --include-data-dir="$GUI_DIR/xhtml=xhtml"
    --include-data-files="$GUI_DIR/icon.ico=icon.ico"
    --include-data-files="$GUI_DIR/info.py=info.py"
    --include-data-files="$GUI_DIR/_optolithiumc.so=_optolithiumc.so"
    --include-data-files="$GUI_DIR/optolithiumc.py=optolithiumc.py"
    --include-data-files="$GUI_DIR/_clipper.so=_clipper.so"
    --include-data-files="$GUI_DIR/clipper.py=clipper.py"
    --include-package=database
    --include-package=views
    --include-package=bson
    --include-package=gdsii
    --include-package=magic
    --include-package=sqlalchemy
    --include-package=psutil
    --remove-output
)

if [ -f "$GUI_DIR/matplotlibrc" ]; then
    NUITKA_ARGS+=(--include-data-files="$GUI_DIR/matplotlibrc=matplotlibrc")
fi

if [ -d "$GUI_DIR/mpl-data" ]; then
    NUITKA_ARGS+=(--include-data-dir="$GUI_DIR/mpl-data=mpl-data")
fi

if [ "$MODE" = "onefile" ]; then
    NUITKA_ARGS+=(--onefile)
else
    NUITKA_ARGS+=(--standalone)
fi

# Run Nuitka compiler
(cd "$GUI_DIR" && "${NUITKA_CMD[@]}" "${NUITKA_ARGS[@]}" "$GUI_DIR/main.py")

# 5. Move output to destination
if [ "$MODE" = "onefile" ]; then
    FINAL_BIN="$OUTPUT_DIR/optolithium"
    cp -f "$BUILD_TMP/optolithium.bin" "$FINAL_BIN" 2>/dev/null || cp -f "$BUILD_TMP/optolithium" "$FINAL_BIN"
    chmod +x "$FINAL_BIN"
    echo "==> Standalone executable created: $FINAL_BIN"
else
    FINAL_DIST="$OUTPUT_DIR/optolithium.dist"
    rm -rf "$FINAL_DIST"
    cp -a "$BUILD_TMP/main.dist" "$FINAL_DIST"
    # Create symlink or rename binary to optolithium
    if [ -f "$FINAL_DIST/main.bin" ]; then
        mv -f "$FINAL_DIST/main.bin" "$FINAL_DIST/optolithium"
    elif [ -f "$FINAL_DIST/main" ]; then
        mv -f "$FINAL_DIST/main" "$FINAL_DIST/optolithium"
    fi
    chmod +x "$FINAL_DIST/optolithium"

    # Bundle native system libraries (e.g. libfftw3)
    for lib in /lib64/libfftw3.so* /usr/lib64/libfftw3.so*; do
        if [ -f "$lib" ]; then
            cp -a "$lib" "$FINAL_DIST/" 2>/dev/null || true
        fi
    done
    echo "==> Standalone distribution created: $FINAL_DIST"
fi

# Clean temporary build directory
rm -rf "$BUILD_TMP"

echo "=========================================================="
echo " Nuitka Standalone Compilation Complete!"
echo " Output: $OUTPUT_DIR"
if [ "$MODE" = "onefile" ]; then
    ls -lh "$OUTPUT_DIR/optolithium"
else
    ls -lh "$OUTPUT_DIR/optolithium.dist/optolithium"
    echo "Total distribution size: $(du -sh "$OUTPUT_DIR/optolithium.dist" | cut -f1)"
fi
echo "=========================================================="
echo "This build has ZERO runtime Python dependencies and can run"
echo "on any Linux x86_64 machine with or without Python installed."
echo "=========================================================="
