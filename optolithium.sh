#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$SCRIPT_DIR/OptolithiumGui"
VENV_DIR="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Optolithium Python environment not found at $VENV_DIR. Creating..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install PyQt5 "numpy<2" scipy matplotlib "sqlalchemy<2" psutil python-magic python-gdsii bson
fi

export PYTHONPATH="$GUI_DIR:$PYTHONPATH"
cd "$GUI_DIR"
exec "$VENV_DIR/bin/python" "$GUI_DIR/main.py" "$@"
