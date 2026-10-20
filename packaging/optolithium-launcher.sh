#!/usr/bin/env bash
# ==============================================================================
# Optolithium Application Launcher
# ==============================================================================
set -e

INSTALL_DIR="/opt/optolithium"
APP_DIR="$INSTALL_DIR/app"

# 1. Check for bundled virtual environment
if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$INSTALL_DIR/venv/bin/python"
# 2. Check for user-specified virtual environment
elif [ -n "$OPTOLITHIUM_VENV" ] && [ -x "$OPTOLITHIUM_VENV/bin/python" ]; then
    PYTHON_BIN="$OPTOLITHIUM_VENV/bin/python"
# 3. Check for existing user cache virtual environment
elif [ -x "${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python" ]; then
    PYTHON_BIN="${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv/bin/python"
# 4. Fallback: Automatically bootstrap user virtual environment
else
    USER_VENV="${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv"
    echo "Optolithium Python environment not found. Initializing in $USER_VENV..."
    python3 -m venv "$USER_VENV"
    "$USER_VENV/bin/pip" install --upgrade pip
    "$USER_VENV/bin/pip" install PyQt5 "numpy<2" scipy matplotlib "sqlalchemy<2" psutil python-magic python-gdsii bson
    PYTHON_BIN="$USER_VENV/bin/python"
fi

export PYTHONPATH="$APP_DIR:$PYTHONPATH"
cd "$APP_DIR"
exec "$PYTHON_BIN" "$APP_DIR/main.py" "$@"

