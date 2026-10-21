#!/usr/bin/env bash
# ==============================================================================
# Optolithium Standalone Application Launcher (Zero-Dependency)
# ==============================================================================
set -e

INSTALL_DIR="/opt/optolithium"
APP_DIR="$INSTALL_DIR/app"
LIB_DIR="$INSTALL_DIR/lib"
VENV_DIR="$INSTALL_DIR/venv"

# 1. Add bundled native shared libraries (e.g. libfftw3) to library path
if [ -d "$LIB_DIR" ]; then
    export LD_LIBRARY_PATH="$LIB_DIR:${LD_LIBRARY_PATH:-}"
fi

# 2. Determine Python runtime
# Detect expected Python minor version from bundled venv site-packages (e.g. python3.12)
REQUIRED_PY=""
for d in "$VENV_DIR"/lib/python3.*; do
    if [ -d "$d" ]; then
        REQUIRED_PY="$(basename "$d")"
        break
    fi
done

PYTHON_BIN=""

# 2a. Priority 1: User explicitly set OPTOLITHIUM_VENV
if [ -n "$OPTOLITHIUM_VENV" ] && [ -x "$OPTOLITHIUM_VENV/bin/python" ]; then
    PYTHON_BIN="$OPTOLITHIUM_VENV/bin/python"

# 2b. Priority 2: Matching system python interpreter (e.g. /usr/bin/python3.12)
elif [ -n "$REQUIRED_PY" ] && command -v "$REQUIRED_PY" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$REQUIRED_PY")"

# 2c. Priority 3: Bundled venv python, verified for version compatibility
elif [ -x "$VENV_DIR/bin/python" ]; then
    VENV_PY_VER="$("$VENV_DIR/bin/python" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    if [ -z "$REQUIRED_PY" ] || [ "$VENV_PY_VER" = "$REQUIRED_PY" ]; then
        PYTHON_BIN="$VENV_DIR/bin/python"
    fi
fi

# 2d. Priority 4: User-level virtualenv in ~/.cache
if [ -z "$PYTHON_BIN" ] && [ -x "${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python" ]; then
    USER_PY_VER="$("${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    if [ -z "$REQUIRED_PY" ] || [ "$USER_PY_VER" = "$REQUIRED_PY" ]; then
        PYTHON_BIN="${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python"
    fi
fi

# 2e. Priority 5: System default python3, verified for compatibility
if [ -z "$PYTHON_BIN" ] && command -v python3 >/dev/null 2>&1; then
    SYS_PY_VER="$(python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    if [ -z "$REQUIRED_PY" ] || [ "$SYS_PY_VER" = "$REQUIRED_PY" ]; then
        PYTHON_BIN="$(command -v python3)"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "================================================================================" >&2
    echo "Error: Optolithium cannot find a compatible Python runtime." >&2
    echo "The bundled application packages require: ${REQUIRED_PY:-python3.12}" >&2
    if command -v python3 >/dev/null 2>&1; then
        echo "Found system default: $(python3 --version 2>&1), which is ABI-incompatible with the bundled libraries." >&2
    fi
    echo "" >&2
    echo "Please install ${REQUIRED_PY:-python3.12} using your system package manager:" >&2
    echo "    Fedora / RHEL:   sudo dnf install -y ${REQUIRED_PY:-python3.12}" >&2
    echo "    Ubuntu / Debian: sudo apt install -y ${REQUIRED_PY:-python3.12}" >&2
    echo "================================================================================" >&2
    exit 1
fi

# 3. Add bundled site-packages and app directory to PYTHONPATH
for sp in "$VENV_DIR"/lib/python*/site-packages; do
    if [ -d "$sp" ]; then
        export PYTHONPATH="$sp:${PYTHONPATH:-}"
    fi
done

export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"
cd "$APP_DIR"
exec "$PYTHON_BIN" "$APP_DIR/main.py" "$@"
