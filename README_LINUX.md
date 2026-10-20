# Optolithium on Linux

Optolithium has been modernized to run natively on Linux with Python 3.12 and modern C++ compilers (GCC 14 / Clang), removing the requirement for Windows and the legacy 32-bit Windows installer.

---

## Quick Start: Launching the Application

To run the application:

```bash
./optolithium.sh
```

Or copy the desktop entry to your user applications menu:

```bash
cp Optolithium.desktop ~/.local/share/applications/
```

The launcher automatically detects and uses the dedicated Python virtual environment located at `~/.cache/optolithium/venv`.

---

## What was Modernized

### 1. C++ Simulation Engine (`OptolithiumC`) & SWIG Bindings
- **Build System**: Upgraded CMake configs from legacy CMake 2.8 syntax to CMake 3.12+ standards with modern Python 3, NumPy, and FFTW3 detection.
- **ArmanPy Bridge**: Upgraded NumPy C-API bindings from Python 2 PyCObject/PyString to modern Python 3 `PyCapsule`, `PyBytes`, `PyLong`, and `NPY_ARRAY_F_CONTIGUOUS` validation for Fortran-ordered Armadillo matrices.
- **SWIG Interface**: Modernized `optolithiumc.i` and `clipper.i` for SWIG 4.x (standard vector template instantiation for `oplc::Region`, output parameter appending, and Python 3 property syntax).
- **All 13 Plugins Rebuilt**: Compiled development rate models (`mack`, `notch`, `enhanced`, `notch_depth`, `enhanced_notch`), mask models (`line1D`, `space1D`, `fiveBarLine`, `line1D_SRAF`), pupil filters (`central_obscuration`), and source shapes (`coherent`, `annular`, `convenient`).

### 2. Python Modernization (`Python 2.7` &rarr; `Python 3.12`)
- **Qt5 Migration**: Implemented Qt5-compatible shims for `QHeaderView`, `QStackedWidget`, and replaced obsolete `QtWebKit` with `QTextBrowser`.
- **SQLAlchemy 2.x Compatibility**: Added custom `hybrid_property` descriptors to support both class-level attribute querying and instance-level attribute access across database models (`Material`, `Resist`, `SourceShape`, `Mask`, etc.).
- **Data Structures & Collections**: Fixed Python 3 iterator/generator incompatibilities (`dict.keys()`, `dict.values()`, `zip`, `range`) in Wafer, Resist, Metrology, and Database views.
- **Path Portability**: Updated dynamic resource and plugin loaders to reference directory roots dynamically via `__file__` instead of static `os.getcwd()` or Windows paths.
- **Filesystem Compatibility**: The project is situated on an `exfat` mount (which does not support POSIX symlinks). The virtual environment is maintained on the host POSIX filesystem (`~/.cache/optolithium/venv`) and integrated seamlessly via `optolithium.sh`.

---

## Rebuilding from Source

If you edit any C++ code or plugins:

```bash
./rebuild_linux.sh
```

### System Dependencies Required for Rebuilding:
- **Fedora / RHEL / Rocky Linux / AlmaLinux**:
  ```bash
  sudo dnf install -y gcc gcc-c++ cmake swig fftw-devel lapack-devel openblas-devel armadillo-devel python3-devel
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt-get install -y build-essential cmake swig libfftw3-dev liblapack-dev libopenblas-dev libarmadillo-dev python3-dev python3-venv
  ```

---

## Verifying Simulation Pipeline

You can run an automated end-to-end simulation test across all 8 lithography simulation stages:

```bash
/home/rudra/.cache/optolithium/venv/bin/python test_full_simulation.py
```

