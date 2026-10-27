# Optolithium Automated Version Control System

Optolithium uses automated [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

The version is defined in a single source of truth:
- **`OptolithiumGui/info.py`** (`__version__ = "X.Y.Z"`)

Whenever the version updates, it is automatically synchronized to:
- `installer/Optolithium.aip` (`ProductVersion`)
- `packaging/optolithium.spec` (`Version`)
- GUI About dialog and packaging binaries

---

## 1. Zero-Touch Automatic Git Hook

Optolithium includes a Git pre-commit hook in `.githooks/pre-commit` that automatically updates the version whenever code changes are committed.

### How It Works

When you run `git commit`:
1. **Change Detection**: The hook checks if staged files contain application or build code (`OptolithiumGui/`, `OptolithiumC/`, `packaging/`, scripts, etc.). If you only changed markdown documentation or `.gitignore`, it leaves the version unchanged.
2. **Commit Type Detection** (Conventional Commits):
   - **Minor Bump (`0.3.0` &rarr; `0.4.0`)**: If your commit message starts with `feat:` or `feat(...)`, or includes `[minor]`, or your branch is `feat/*`.
   - **Patch Bump (`0.3.0` &rarr; `0.3.1`)**: If your commit is a `fix:`, `perf:`, `chore:`, `refactor:`, or general code change, or includes `[patch]`.
   - **Major Bump (`0.3.0` &rarr; `1.0.0`)**: If your commit contains `BREAKING CHANGE` or `!:`.
3. **Automatic Staging**: The updated `OptolithiumGui/info.py` and configuration files are automatically staged into the commit being created.
4. **Manual Override Respect**: If you manually edited `OptolithiumGui/info.py` in your commit, the hook respects your explicit version and does not overwrite it.

### Enabling / Disabling the Hook

The hook is pre-configured via Git's `core.hooksPath`:
```bash
# Enable hook (already configured)
./version.sh install-hook

# Disable hook
./version.sh uninstall-hook

# Skip bump for a single commit
git commit -m "chore: something [no-bump]"
# OR
OPTOLITHIUM_NO_BUMP=1 git commit -m "..."
# OR
git commit --no-verify -m "..."
```

---

## 2. Command-Line Interface (`./version.sh`)

You can inspect or bump versions on demand using `./version.sh` (or `python3 tools/version_manager.py`):

```bash
# View current version
./version.sh
# 0.3.0

# View detailed version & Git status
./version.sh status

# Bump patch: 0.3.0 -> 0.3.1
./version.sh bump patch

# Bump minor: 0.3.0 -> 0.4.0
./version.sh bump minor

# Bump major: 0.3.0 -> 1.0.0
./version.sh bump major

# Automatically detect bump based on git history since last version change
./version.sh auto

# Set an explicit version
./version.sh set 0.4.0

# Automatically commit and tag the new version
./version.sh bump minor --commit --tag
```

---

## 3. Package Building Integration

You can also trigger a version bump directly when building packages:

```bash
# Build RPM & DEB with a patch bump (e.g. 0.3.0 -> 0.3.1)
./build_packages.sh --bump-patch

# Build packages with a minor bump (e.g. 0.3.0 -> 0.4.0)
./build_packages.sh --bump-minor

# Build packages with automatic version detection from commit history
./build_packages.sh --bump-auto
```

# Automated Versioning Verified
