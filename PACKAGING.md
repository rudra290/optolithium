# Optolithium Linux Packaging Guide (.rpm & .deb)

This guide explains how to generate **`.rpm`** (Fedora, RHEL, Rocky Linux) and **`.deb`** (Ubuntu, Debian, Linux Mint) packages and repositories for Optolithium.

---

## 1. Quick Overview

| Distribution Family | Package Format | Package Manager | Repository Config File | Repo Metadata Generator |
|---|---|---|---|---|
| **RHEL / Rocky / Fedora** | `.rpm` | `dnf` / `rpm` | `optolithium.repo` (`/etc/yum.repos.d/`) | `createrepo_c` |
| **Debian / Ubuntu / Mint** | `.deb` | `apt` / `dpkg` | `optolithium.list` (`/etc/apt/sources.list.d/`) | `dpkg-scanpackages` / internal |

---

## 2. Quick Start: One-Click Build

To build **both** `.rpm` and `.deb` packages as well as their repository configurations:

```bash
./build_packages.sh
```

### Targeted Builds:
```bash
# Build only RPM & DNF repo
./build_packages.sh --rpm-only

# Build only DEB & APT repo
./build_packages.sh --deb-only

# Bundle dedicated Python virtualenv for offline / air-gapped systems
./build_packages.sh --bundle-venv
```

---

## 3. Package Artifacts Output (`dist/`)

After running the build, the artifacts are organized in `dist/`:

```
dist/
├── dist/optolithium.repo             # DNF repository configuration
├── dist/optolithium.list             # APT traditional source list
├── dist/optolithium.sources          # APT modern DEB822 source file
├── rpm/
│   └── optolithium-0.3.0-1.el10.x86_64.rpm
├── dnf-repo/
│   ├── optolithium-0.3.0-1.el10.x86_64.rpm
│   └── optolithium.repo
├── deb/
│   └── optolithium_0.3.0-1_amd64.deb
└── apt-repo/
    ├── optolithium_0.3.0-1_amd64.deb
    ├── Packages
    ├── Packages.gz
    ├── Release
    ├── optolithium.list
    └── optolithium.sources
```

---

## 4. Debian / Ubuntu (`.deb`) Guide

### Building `.deb`
Use the dedicated packaging script:
```bash
./packaging/build_deb.sh --slim
```
*Note: The script automatically detects whether `dpkg-deb` is installed. If not (e.g. running on Rocky/RHEL/Fedora), it automatically uses a portable internal standard `ar` + `tar` packager to produce a 100% compliant Debian binary package.*

### Installing `.deb` on Debian / Ubuntu

#### Option A: Direct Installation via APT (Recommended)
```bash
sudo apt install ./dist/deb/optolithium_0.3.0-1_amd64.deb
```

#### Option B: Direct Installation via dpkg
```bash
sudo dpkg -i ./dist/deb/optolithium_0.3.0-1_amd64.deb
sudo apt-get install -f
```

#### Option C: Local APT Repository
1. Generate APT repository metadata:
   ```bash
   ./packaging/create_apt_repo.sh
   ```
2. Add the repository to `/etc/apt/sources.list.d/`:
   ```bash
   sudo cp dist/optolithium.list /etc/apt/sources.list.d/
   sudo apt update
   sudo apt install optolithium
   ```

---

## 5. RHEL / Rocky / Fedora (`.rpm`) Guide

### Building `.rpm`
```bash
./packaging/build_rpm.sh --slim
```

### Installing `.rpm` with DNF

#### Option A: Direct Installation via DNF (Recommended)
```bash
sudo dnf install ./dist/rpm/optolithium-0.3.0-1.el10.x86_64.rpm
```

#### Option B: Local DNF Repository (`.repo` file)
1. Generate DNF repository metadata:
   ```bash
   ./packaging/create_dnf_repo.sh
   ```
2. Add repository configuration:
   ```bash
   sudo cp dist/optolithium.repo /etc/yum.repos.d/
   sudo dnf makecache
   sudo dnf install optolithium
   ```

---

## 6. Installed Files Structure

Both packages install following standard Linux system conventions:

| Path | Purpose |
|---|---|
| `/opt/optolithium/app/` | Application codebase, views, options, resources |
| `/opt/optolithium/app/*.so` | Core compiled C++ libraries (`_optolithiumc.so`, `_clipper.so`) |
| `/opt/optolithium/app/plugins/` | All 13 compiled C++ lithography plugins |
| `/opt/optolithium/bin/optolithium` | Smart launcher script |
| `/usr/bin/optolithium` | Global command symlink |
| `/usr/share/applications/optolithium.desktop` | Application menu desktop shortcut |
| `/usr/share/icons/hicolor/128x128/apps/optolithium.png` | System application icon |
| `/usr/share/pixmaps/optolithium.png` | System pixmap icon |

---

## 7. Uninstalling

- **Debian / Ubuntu**:
  ```bash
  sudo apt remove optolithium
  ```
- **RHEL / Rocky / Fedora**:
  ```bash
  sudo dnf remove optolithium
  ```
