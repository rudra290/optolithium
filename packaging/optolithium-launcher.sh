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
if [ -x "$VENV_DIR/bin/python" ]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
elif [ -n "$OPTOLITHIUM_VENV" ] && [ -x "$OPTOLITHIUM_VENV/bin/python" ]; then
    PYTHON_BIN="$OPTOLITHIUM_VENV/bin/python"
elif [ -x "${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python" ]; then
    PYTHON_BIN="${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Error: Python 3 not found on this system." >&2
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
