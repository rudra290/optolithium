#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"
PYTHON_BIN="$(command -v python3)"

echo "==> Using Python: $("$PYTHON_BIN" --version 2>&1) at $PYTHON_BIN"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install PyQt5 numpy scipy matplotlib "sqlalchemy<2" psutil python-magic python-gdsii bson
fi

VENV_PYTHON="$VENV_DIR/bin/python"

PYTHON_INCLUDE="$("$VENV_PYTHON" -c "import sysconfig; print(sysconfig.get_path('include'))")"
NUMPY_INCLUDE="$("$VENV_PYTHON" -c "import numpy; print(numpy.get_include())")"
PYTHON_LIB="$("$VENV_PYTHON" -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")"

export PATH="$VENV_DIR/bin:$PATH"

echo "=== 1. Building OptolithiumC Core Library ==="
rm -rf "$REPO_DIR/OptolithiumC/build"
mkdir -p "$REPO_DIR/OptolithiumC/build"
cmake -B "$REPO_DIR/OptolithiumC/build" -S "$REPO_DIR/OptolithiumC" \
    -DCMAKE_BUILD_TYPE=Release \
    -DPython_EXECUTABLE="$VENV_PYTHON" \
    -DPython_INCLUDE_DIR="$PYTHON_INCLUDE" \
    -DPython_NumPy_INCLUDE_DIR="$NUMPY_INCLUDE"

cmake --build "$REPO_DIR/OptolithiumC/build" -j"$(nproc)"

cp -f "$REPO_DIR/OptolithiumC/build/_optolithiumc.so" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/optolithiumc.py" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/_clipper.so" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/clipper.py" "$REPO_DIR/OptolithiumGui/"

echo "=== 2. Installing Plugins ==="
for plugin_group in dev_models masks pupil_filters source_shapes; do
    mkdir -p "$REPO_DIR/OptolithiumGui/plugins/$plugin_group"
    find "$REPO_DIR/OptolithiumC/build/plugins/build/$plugin_group" -name "*.so" -exec cp -f {} "$REPO_DIR/OptolithiumGui/plugins/$plugin_group/" \; 2>/dev/null || true
done

echo "=== Build finished successfully! ==="
echo "Run './optolithium.sh' to launch Optolithium."

