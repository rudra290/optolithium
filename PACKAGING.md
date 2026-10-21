# Optolithium Packaging Guide (.rpm, .deb, and .msi)

This guide explains how to generate installation packages for Optolithium across all major operating systems:
- **`.rpm`** (Fedora, RHEL, Rocky Linux, AlmaLinux)
- **`.deb`** (Ubuntu, Debian, Linux Mint)
- **`.msi`** (Microsoft Windows Installer)

---

## 1. Quick Overview

| Platform | Format | Package Manager / Tool | Config / Spec File | Generator Script |
|---|---|---|---|---|
| **RHEL / Rocky / Fedora** | `.rpm` | `dnf` / `rpm` | `optolithium.spec` | `./packaging/build_rpm.sh` |
| **Debian / Ubuntu / Mint** | `.deb` | `apt` / `dpkg` | `DEBIAN/control` | `./packaging/build_deb.sh` |
| **Microsoft Windows** | `.msi` | Windows Installer / WiX | `optolithium.wxs` | `./packaging/build_msi.sh` |

---

## 2. Quick Start: Zero-Dependency Build

By default, all builds produce **fully self-contained, zero-dependency** packages. All Python dependencies (`PyQt5`, `numpy`, `scipy`, `matplotlib`, `SQLAlchemy`, `psutil`, `bson`, `python-gdsii`, `python-magic`) and native C++ simulation libraries (including `libfftw3`) are bundled inside the package so target machines require **zero pip installs, zero external development packages, and zero internet connection**.

```bash
# Build standalone Linux packages (.rpm and .deb) + repositories:
./build_packages.sh
```

### Build Options:
```bash
# Build standalone Linux packages (.rpm and .deb) + repositories:
./build_packages.sh

# Build 100% standalone native binary with Nuitka (ZERO Python dependency, runs on any machine):
./build_packages.sh --nuitka-only
# Or compile RPM and DEB packages using Nuitka native binaries:
./build_packages.sh --nuitka

# Build a single self-extracting executable with Nuitka:
./packaging/build_nuitka.sh --onefile

# Build all platforms (.rpm, .deb, and Windows .msi staging/installer):
./build_packages.sh --all

# Build only standalone RPM & DNF repo:
./build_packages.sh --rpm-only

# Build only standalone DEB & APT repo:
./build_packages.sh --deb-only

# Build only Windows .msi installer:
./build_packages.sh --msi-only

# Lightweight slim build (relies on host Python virtual environment):
./build_packages.sh --slim
```

---

## 3. Package Artifacts Output (`dist/`)

All generated distribution files are organized in `dist/`:

```
dist/
├── dist/optolithium.repo             # DNF repository configuration
├── dist/optolithium.list             # APT traditional source list
├── dist/optolithium.sources          # APT modern DEB822 source file
├── rpm/
│   └── optolithium-0.3.0-1.el10.x86_64.rpm
├── dnf-repo/
│   └── optolithium-0.3.0-1.el10.x86_64.rpm
├── deb/
│   └── optolithium_0.3.0-1_amd64.deb
├── apt-repo/
│   ├── optolithium_0.3.0-1_amd64.deb
│   └── Packages.gz
├── msi/
│   └── optolithium-0.3.0.msi         # Windows Installer package
└── msi-staging/                      # WiX source and Windows build files
    ├── optolithium.wxs               # Generated WiX XML specification
    ├── optolithium.bat               # Windows application launcher
    ├── optolithium-cli.bat           # Windows command-line launcher
    ├── build_msi.bat                 # Windows WiX v3 builder
    ├── build_msi_v4.bat              # Windows WiX v4/v5 builder
    └── build_msi.ps1                 # Windows PowerShell builder
```

---

## 4. Windows (`.msi`) Guide

The MSI packaging system creates a standard Windows Installer package featuring:
- Installation into `C:\Program Files\Optolithium`
- Start Menu application shortcut and uninstaller
- Desktop shortcut
- Windows Add/Remove Programs integration
- Dual launchers (`optolithium.bat` GUI launcher and `optolithium-cli.bat` console launcher)

### Building the MSI:

#### Method A: Directly on Linux (via `msitools`)
You can cross-compile the `.msi` directly on Linux without Windows or Wine using `msitools` (`wixl`):

1. Install `msitools`:
   ```bash
   # Fedora / RHEL / Rocky Linux
   sudo dnf install -y msitools

   # Ubuntu / Debian
   sudo apt install -y msitools
   ```

2. Build the package:
   ```bash
   ./packaging/build_msi.sh
   # Output: dist/msi/optolithium-0.3.0.msi
   ```

#### Method B: On Windows (using WiX Toolset)
1. Run `./packaging/build_msi.sh` (or `./build_packages.sh --msi`) to generate the complete staging directory at `dist/msi-staging/`.
2. Copy `dist/msi-staging/` to a Windows machine.
3. Open a Command Prompt or PowerShell in `msi-staging` and run:
   - For **WiX Toolset v3**:
     ```cmd
     build_msi.bat
     ```
   - For **WiX Toolset v4/v5** (`dotnet tool install --global wix`):
     ```cmd
     build_msi_v4.bat
     ```
   - Or directly in PowerShell:
     ```powershell
     wix build optolithium.wxs -o optolithium-0.3.0.msi
     ```

#### Method C: Advanced Installer
The legacy Advanced Installer project file is preserved at [`installer/Optolithium.aip`](installer/Optolithium.aip) and can be opened in Caphyon Advanced Installer on Windows.

---

## 5. Debian / Ubuntu (`.deb`) Guide

### Building `.deb`:
```bash
./packaging/build_deb.sh --slim
```

### Installing on Debian / Ubuntu:
```bash
# Recommended (resolves dependencies automatically):
sudo apt install ./dist/deb/optolithium_0.3.0-1_amd64.deb

# Or using local repository:
sudo cp dist/optolithium.list /etc/apt/sources.list.d/
sudo apt update
sudo apt install optolithium
```

---

## 6. RHEL / Rocky / Fedora (`.rpm`) Guide

### Building `.rpm`:
```bash
./packaging/build_rpm.sh --slim
```

### Installing with DNF:
```bash
# Direct install:
sudo dnf install ./dist/rpm/optolithium-0.3.0-1.el10.x86_64.rpm

# Or using local repository:
sudo cp dist/optolithium.repo /etc/yum.repos.d/
sudo dnf makecache
sudo dnf install optolithium
```

---

## 7. Uninstalling

- **Windows**: Control Panel &rarr; Add or Remove Programs &rarr; Uninstall Optolithium (or `msiexec /x optolithium-0.3.0.msi`)
- **Debian / Ubuntu**: `sudo apt remove optolithium`
- **RHEL / Rocky / Fedora**: `sudo dnf remove optolithium`
