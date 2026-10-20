# Optolithium #

![Logo.png](https://github.com/xthebat/optolithium/blob/master/Logo.png)

## What is it? ##

Optolithium is an optical lithography (see [Photolithography](http://en.wikipedia.org/wiki/Photolithography)) modelling software that allows calculating results at the different steps of the process. It is open-source software aimed at teaching students the basics of micro- and nano-fabrication processes. Optolithium refers to [computational lithography](http://en.wikipedia.org/wiki/Computational_lithography) software and simulates the complete optical lithography process pipeline:

* **Diffraction Pattern** (mask diffraction in pupil plane)
* **Aerial Image** (light intensity distribution in air)
* **Image in Resist** (standing waves and light distribution inside photoresist)
* **Exposed Latent Image in Resist** (photoactive compound / PAC concentration)
* **Post-Exposure Bake (PEB) Latent Image** (diffusion of photoactive compound)
* **Develop Time Contours** (resist development front propagation)
* **Resist Profile** (final developed 2D resist cross-section)
* **Simulation Sets** (automated multi-variable parameter sweeps and Focus-Exposure Matrix analysis)

![Optolithium-Profile.png](https://github.com/xthebat/optolithium/blob/master/Profile.png)

Screenshot of the main window of Optolithium software with simulation results of aerial image in resist showing the standing waves effect:

![Optolithium_IR.png](https://github.com/xthebat/optolithium/blob/master/Profile_IR.png)

---

## Modernization & Linux Support ##

Optolithium has been modernized from its original 2015 codebase (Python 2.7 / Windows-only installer) to run natively on **Linux** (Rocky Linux, RHEL, Fedora, Ubuntu, Debian, etc.) using **Python 3.12** and **PyQt5**.

### Key Modernization Highlights:
- **Python 3.12 & PyQt5**: Fully ported from Python 2.7 and PySide to Python 3.12 and PyQt5 with Qt5-compatible layout and model reset implementations.
- **Modern C++ & SWIG 4.x**: Updated C++ simulation core and SWIG interface bindings for GCC 14 / Clang, CMake 3.12+, and Python 3 C-API (`PyCapsule`, `PyBytes`, `PyLong`).
- **64-bit Linux Plugins**: Recompiled all 13 C plugins (resist development models, 1D/2D masks, pupil filters, source shapes) as native 64-bit `.so` libraries.
- **SQLAlchemy 2.x & Legacy BSON**: Modernized database models with custom hybrid properties and automatic recursive byte-string normalization for legacy Python 2 `.opl` files.
- **Matplotlib 3.8+ Compatibility**: Updated simulation drawing and stem plots for modern `LineCollection` and horizontal stem orientation.

---

## Quick Start on Linux ##

### Running Directly via Script

Optolithium includes a self-contained launcher that automatically sets up and uses a dedicated virtual environment:

```bash
./optolithium.sh
```

To install the desktop application shortcut into your system application menu:

```bash
cp Optolithium.desktop ~/.local/share/applications/
```

### Installing via Linux Packages (.rpm & .deb)

Optolithium provides automated packaging scripts for all major Linux distributions:

#### Build Packages (One-Click):
```bash
# Builds both .rpm (DNF) and .deb (APT) packages
./build_packages.sh
```

#### Install on Fedora / RHEL / Rocky Linux / AlmaLinux (.rpm):
```bash
sudo dnf install -y dist/rpm/optolithium-*.rpm
```

#### Install on Ubuntu / Debian / Linux Mint (.deb):
```bash
sudo apt install -y ./dist/deb/optolithium_*.deb
```

For detailed repository configuration, offline/air-gapped bundle builds, and APT/DNF local repos, see [PACKAGING.md](PACKAGING.md).

---

## Rebuilding from Source ##

To rebuild the C++ simulation core and all 13 plugins:

```bash
./rebuild_linux.sh
```

### Build Dependencies:
* **Fedora / RHEL / Rocky Linux / AlmaLinux**:
  ```bash
  sudo dnf install -y gcc gcc-c++ cmake swig fftw-devel lapack-devel openblas-devel armadillo-devel python3-devel
  ```
* **Ubuntu / Debian**:
  ```bash
  sudo apt-get install -y build-essential cmake swig libfftw3-dev liblapack-dev libopenblas-dev libarmadillo-dev python3-dev python3-venv
  ```

---

## Papers ##

Note: papers were created in the Russian language.

- [Optical lithography basics](https://github.com/xthebat/optolithium/releases/download/papers/Optical.Lithography.Simulation.Basics.pdf)
- [Lithography lecture](https://github.com/xthebat/optolithium/releases/download/papers/4.Lecture.ppt.pdf)
- [Simulation lecture](https://github.com/xthebat/optolithium/releases/download/papers/7.Lecture.ppt.pdf)
- [Optolithium lecture](https://github.com/xthebat/optolithium/releases/download/papers/8.Lecture.Optolithium.ppt.pdf)

---

## Architecture & Internals ##

The program consists of two primary modules:

* **The Core (`OptolithiumC`)**: High-performance C++11 numerical engine computing Fourier optics, matrix calculations, light propagation in thin films, exposure kinetics, diffusion, and level set contour propagation.
* **The GUI (`OptolithiumGui`)**: Python/PyQt5 user interface providing interactive parameters editing, real-time plotting, GDSII mask import, and material databases.

### Plugin System
Optolithium features a modular C plugin architecture. Anyone can implement custom models in C using `<OPTOLITHIUM_SRC>/OptolithiumC/include/optolithium.h`:

* **Photomask models**: 1D binary space, 1D binary line, 1D binary line with SRAF, 5-bar line array
* **Source shapes**: Coherent, annular, conventional / partially coherent
* **Pupil filters**: Central obscuration
* **Resist development rate models**: Mack, Enhanced Mack, Notch, Notch Depth, Enhanced Notch

---

## Fourier Transform Engine ##

Light diffraction simulation relies heavily on 2D Fourier transforms. Optolithium supports both its built-in Fourier transform library and the industry-standard [FFTW3](http://www.fftw.org/) library. FFTW3 can be toggled via `OPTOLITHIUMC_USE_FFTW_LIBRARY` in `OptolithiumC/CMakeLists.txt`.

---

## Dependencies ##

### Python Modules (`OptolithiumGui`)
* Python >= 3.8 (tested on Python 3.12)
* PyQt5
* NumPy (< 2.0)
* SciPy
* Matplotlib
* SQLAlchemy (< 2.0 or 2.x with compatibility layer)
* python-gdsii
* bson
* psutil
* python-magic

### Core Libraries (`OptolithiumC`)
* Armadillo (C++ linear algebra library)
* SWIG (>= 3.0.5, tested on SWIG 4.x)
* FFTW3
* OpenBLAS / LAPACK
* Clipper (polygon clipping library)
* LSMLIB (level set method library)
* Easylogging++

---

## License ##

Copyright © 2014-2015 *Alexei Gladkikh*

This software is dual-licensed: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version only for NON-COMMERCIAL usage.

Third-party libraries used in this project are subject to their respective open-source licenses:
* **Armadillo**: Mozilla Public License 2.0 (MPL)
* **ArmaNpy**: GNU Lesser General Public License (LGPL)
* **Clipper**: Boost Software License
* **LSMLIB**: BSD License
* **Easylogging++**: MIT License
