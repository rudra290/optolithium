#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${OPTOLITHIUM_VENV:-${XDG_CACHE_HOME:-$HOME/.cache}/optolithium/venv}"
PYTHON_BIN="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    if command -v python3.12 >/dev/null 2>&1; then
        BASE_PY="python3.12"
    else
        BASE_PY="python3"
    fi
    "$BASE_PY" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install PyQt5 "numpy<2" scipy matplotlib "sqlalchemy<2" psutil python-magic python-gdsii bson
fi

PYTHON_INCLUDE="$("$PYTHON_BIN" -c "import sysconfig; print(sysconfig.get_path('include'))")"
NUMPY_INCLUDE="$("$PYTHON_BIN" -c "import numpy; print(numpy.get_include())")"
PYTHON_LIB="$("$PYTHON_BIN" -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")"

echo "=== 1. Building OptolithiumC Core Library ==="
mkdir -p "$REPO_DIR/OptolithiumC/build"
cmake -B "$REPO_DIR/OptolithiumC/build" -S "$REPO_DIR/OptolithiumC" \
    -DCMAKE_BUILD_TYPE=Release \
    -DPython_EXECUTABLE="$PYTHON_BIN" \
    -DPython_INCLUDE_DIR="$PYTHON_INCLUDE" \
    -DPython_NumPy_INCLUDE_DIR="$NUMPY_INCLUDE"

cmake --build "$REPO_DIR/OptolithiumC/build" -j"$(nproc)"

cp -f "$REPO_DIR/OptolithiumC/build/_optolithiumc.so" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/optolithiumc.py" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/_clipper.so" "$REPO_DIR/OptolithiumGui/"
cp -f "$REPO_DIR/OptolithiumC/build/clipper.py" "$REPO_DIR/OptolithiumGui/"

echo "=== 2. Building C Plugins ==="
for plugin_group in dev_models masks pupil_filters source_shapes; do
    echo "Building $plugin_group plugins..."
    cmake -B "$REPO_DIR/Plugins/$plugin_group/build" -S "$REPO_DIR/Plugins/$plugin_group" \
        -DCMAKE_BUILD_TYPE=Release \
        -DARMADILLO_INCLUDE_DIR="$REPO_DIR/OptolithiumC/third_party/armadillo/include"
    cmake --build "$REPO_DIR/Plugins/$plugin_group/build" -j"$(nproc)"

    mkdir -p "$REPO_DIR/OptolithiumGui/plugins/$plugin_group"
    find "$REPO_DIR/Plugins/$plugin_group/build" -name "*.so" -exec cp -f {} "$REPO_DIR/OptolithiumGui/plugins/$plugin_group/" \;
done

echo "=== Build finished successfully! ==="
echo "Run './optolithium.sh' to launch Optolithium."

