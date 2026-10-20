# Optolithium Packaging Guide (.rpm & DNF)

This guide explains how to generate `.rpm` packages and configure DNF repositories for Optolithium on RPM-based Linux distributions (Rocky Linux, RHEL, CentOS Stream, Fedora, AlmaLinux, etc.).

---

## 1. Quick Overview: RPM vs DNF

- **`.rpm` (Red Hat Package Manager)**: The standard binary package file format for Fedora / RHEL / Rocky Linux systems. Contains compiled binaries, Python libraries, desktop shortcuts, icons, and metadata.
- **DNF (Dandified YUM)**: The package manager command (`dnf install`, `dnf update`) used to install and manage `.rpm` files and their dependencies.
- **`.repo`**: The repository configuration file format used by DNF (stored in `/etc/yum.repos.d/`) to discover and download `.rpm` packages from local or remote repositories.

---

## 2. Quick Start: One-Click Build

To build both the `.rpm` package and the DNF repository configuration:

```bash
./build_packages.sh
```

This will produce:
- **RPM Package**: `dist/rpm/optolithium-0.3.0-1.el10.x86_64.rpm`
- **DNF Repository**: `dist/dnf-repo/`
- **DNF Repo Config**: `dist/optolithium.repo`

---

## 3. Building the `.rpm` Package

The dedicated script `packaging/build_rpm.sh` wraps `rpmbuild` with custom staging and handles non-POSIX mounts (e.g. exFAT) by utilizing `/tmp`:

### Standard / Slim Build (~2 MB)
Packages the compiled C++ simulation engines, plugins, and Python GUI:
```bash
./packaging/build_rpm.sh --slim
```

### Self-Contained Offline / Air-Gapped Build
Packages Optolithium along with a dedicated pre-built Python virtual environment so no pip compilation or internet connection is required on target machines:
```bash
./packaging/build_rpm.sh --bundle-venv
```

### Options for `build_rpm.sh`
- `--slim`: Build slim package (default).
- `--bundle-venv`: Bundle complete Python virtualenv.
- `--rebuild`: Force recompilation of C++ engine and plugins prior to packaging.
- `--output-dir <path>`: Custom destination folder (default: `dist/rpm`).
- `--version <x.y.z>`: Override package version.
- `--release <num>`: Override release number (default: 1).

---

## 4. Installing with DNF

You can install the generated package on any Rocky Linux / RHEL / Fedora system using one of the following methods:

### Method A: Direct DNF Installation (Fastest)
DNF can directly resolve and install local `.rpm` files:
```bash
sudo dnf install ./dist/rpm/optolithium-0.3.0-1.el10.x86_64.rpm
```

### Method B: Install via Local DNF Repository
1. Generate repository metadata and configuration:
   ```bash
   ./packaging/create_dnf_repo.sh
   ```
2. Copy the generated `.repo` configuration into DNF's repository directory:
   ```bash
   sudo cp dist/optolithium.repo /etc/yum.repos.d/
   ```
3. Update DNF cache and install:
   ```bash
   sudo dnf makecache
   sudo dnf install optolithium
   ```

### Method C: One-off Install via `--repofrompath`
```bash
sudo dnf --repofrompath=optolithium,$(pwd)/dist/dnf-repo --nogpgcheck install optolithium
```

---

## 5. What the Package Installs

| Path | Purpose |
|---|---|
| `/opt/optolithium/app/` | Python application, modules, views, resources |
| `/opt/optolithium/app/*.so` | Compiled core C++ SWIG libraries (`_optolithiumc.so`, `_clipper.so`) |
| `/opt/optolithium/app/plugins/` | All 13 compiled C++ lithography plugins |
| `/opt/optolithium/bin/optolithium` | Smart launcher script |
| `/usr/bin/optolithium` | Global command symlink |
| `/usr/share/applications/optolithium.desktop` | Application menu desktop shortcut |
| `/usr/share/icons/hicolor/128x128/apps/optolithium.png` | System application icon |

---

## 6. Uninstalling
To cleanly uninstall Optolithium using DNF:
```bash
sudo dnf remove optolithium
```

