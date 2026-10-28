#!/usr/bin/env python3
"""
Optolithium Automated Semantic Version Manager (SemVer)
===============================================
Automates Semantic Versioning (SemVer: MAJOR.MINOR.PATCH) for Optolithium.
Synchronizes version across:
  - OptolithiumGui/info.py (master source of truth)
  - installer/Optolithium.aip
  - packaging/optolithium.spec

Features:
  - Bump patch, minor, or major version
  - Automatic bump based on Conventional Commits (feat -> minor, fix/other -> patch, BREAKING -> major)
  - Pre-commit Git Hook integration for zero-touch automatic versioning on code changes
  - Git tagging and repository synchronization
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Paths relative to repository root
REPO_ROOT = Path(__file__).resolve().parent.parent
INFO_PY = REPO_ROOT / "OptolithiumGui" / "info.py"
AIP_FILE = REPO_ROOT / "installer" / "Optolithium.aip"
SPEC_FILE = REPO_ROOT / "packaging" / "optolithium.spec"
MAN_FILE = REPO_ROOT / "packaging" / "optolithium.1"
GITHOOKS_DIR = REPO_ROOT / ".githooks"
GIT_HOOK_PRE_COMMIT = GITHOOKS_DIR / "pre-commit"

# Code file extensions that warrant an automated version bump
CODE_EXTENSIONS = {
    ".py", ".c", ".cpp", ".cxx", ".cc", ".h", ".hpp", ".hxx",
    ".i", ".sh", ".ui", ".qrc", ".json", ".spec", ".wxs", ".cmake", ".1"
}

# Directories considered source code
CODE_DIRECTORIES = {"OptolithiumGui", "OptolithiumC", "packaging"}

SEMVER_REGEX = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def read_current_version() -> str:
    """Read the master version string from OptolithiumGui/info.py."""
    if not INFO_PY.exists():
        raise FileNotFoundError(f"Master version file not found: {INFO_PY}")
    content = INFO_PY.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"Could not parse __version__ from {INFO_PY}")
    return match.group(1).strip()


def parse_semver(version_str: str):
    """Parse version string into (major, minor, patch, prerelease)."""
    match = SEMVER_REGEX.match(version_str)
    if not match:
        raise ValueError(f"Invalid SemVer string '{version_str}'. Expected format: X.Y.Z")
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(4) or ""
    return major, minor, patch, prerelease


def calculate_bump(version_str: str, bump_type: str) -> str:
    """Calculate the new version string given a bump type (major, minor, patch)."""
    major, minor, patch, _ = parse_semver(version_str)
    bump_type = bump_type.lower()
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown bump type '{bump_type}'. Choose from 'major', 'minor', 'patch'.")


def sync_version_to_files(new_version: str):
    """Write the new version string across all project files."""
    # 1. OptolithiumGui/info.py
    if INFO_PY.exists():
        content = INFO_PY.read_text(encoding="utf-8")
        updated = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{new_version}"',
            content
        )
        if not updated.endswith("\n"):
            updated += "\n"
        INFO_PY.write_text(updated, encoding="utf-8")

    # 2. installer/Optolithium.aip (preserve CRLF if present)
    if AIP_FILE.exists():
        raw = AIP_FILE.read_bytes()
        crlf = b"\r\n" in raw
        content = raw.decode("utf-8", "ignore")
        updated = re.sub(
            r'<ROW Property="ProductVersion" Value="[^"]+" Type="32"/>',
            f'<ROW Property="ProductVersion" Value="{new_version}" Type="32"/>',
            content
        )
        if crlf:
            updated = updated.replace("\r\n", "\n").replace("\n", "\r\n")
        AIP_FILE.write_bytes(updated.encode("utf-8"))

    # 3. packaging/optolithium.spec
    if SPEC_FILE.exists():
        content = SPEC_FILE.read_text(encoding="utf-8")
        updated = re.sub(
            r'Version:\s*%\{\?pkg_version\}%\{!\?pkg_version:[^}]+\}',
            f'Version:        %{{?pkg_version}}%{{!?pkg_version:{new_version}}}',
            content
        )
        SPEC_FILE.write_text(updated, encoding="utf-8")

    # 4. packaging/optolithium.1
    if MAN_FILE.exists():
        content = MAN_FILE.read_text(encoding="utf-8")
        updated = re.sub(
            r'(\.TH\s+OPTOLITHIUM\s+1\s+"[^"]*"\s+"Optolithium\s+)[^"]+(")',
            f'\\g<1>{new_version}\\g<2>',
            content
        )
        MAN_FILE.write_text(updated, encoding="utf-8")


def run_git(args: list, check: bool = True) -> str:
    """Helper to run git commands in REPO_ROOT."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=check
    )
    return result.stdout.strip()


def get_git_info():
    """Retrieve current git context (commit, branch, tag, distance)."""
    try:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False) or "unknown"
        commit = run_git(["rev-parse", "--short", "HEAD"], check=False) or "unknown"
        describe = run_git(["describe", "--tags", "--always"], check=False) or "unknown"
        is_dirty = bool(run_git(["status", "--porcelain"], check=False))
        
        # Commits since info.py was last changed in git
        last_info_commit = run_git(["log", "-n", "1", "--pretty=format:%H", "--", "OptolithiumGui/info.py"], check=False)
        commits_since = 0
        if last_info_commit:
            count = run_git(["rev-list", "--count", f"{last_info_commit}..HEAD"], check=False)
            commits_since = int(count) if count.isdigit() else 0

        return {
            "branch": branch,
            "commit": commit,
            "describe": describe,
            "is_dirty": is_dirty,
            "commits_since_last_bump": commits_since
        }
    except Exception:
        return {
            "branch": "unknown",
            "commit": "unknown",
            "describe": "unknown",
            "is_dirty": False,
            "commits_since_last_bump": 0
        }


def detect_bump_type_from_commits(commits_range: str = None) -> str:
    """
    Analyze commit messages in range using Conventional Commits:
      - 'BREAKING CHANGE' or '!:' -> major
      - 'feat' or 'feat(...)'     -> minor
      - 'fix', 'chore', etc.      -> patch
    """
    if not commits_range:
        last_info_commit = run_git(["log", "-n", "1", "--pretty=format:%H", "--", "OptolithiumGui/info.py"], check=False)
        if last_info_commit:
            commits_range = f"{last_info_commit}..HEAD"
        else:
            commits_range = "HEAD"

    try:
        messages = run_git(["log", "--pretty=format:%s", commits_range], check=False)
    except Exception:
        messages = ""

    if not messages:
        return "patch"

    lines = messages.splitlines()
    has_major = any("BREAKING CHANGE" in l or "!:" in l for l in lines)
    has_minor = any(re.match(r"^feat(\([^\)]+\))?!?:", l) for l in lines)

    if has_major:
        return "major"
    elif has_minor:
        return "minor"
    return "patch"


def find_git_commit_cmdline():
    """Traverse parent processes to locate the git commit command line."""
    pid = os.getpid()
    for _ in range(6):
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("PPid:"):
                        pid = int(line.split()[1])
                        break
            if pid <= 1:
                break
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                parts = [p.decode("utf-8", "ignore") for p in f.read().split(bytes([0])) if p]
            if parts and ("git" in Path(parts[0]).name):
                return parts
        except Exception:
            break
    return []


def detect_bump_from_cmdline_or_env() -> str:
    """Inspect environment variable or parent git process command line for commit message."""
    # 1. Environment variable BUMP
    env_bump = os.environ.get("BUMP", "").strip().lower()
    if env_bump in ("major", "minor", "patch"):
        return env_bump

    # 2. Inspect parent git process cmdline for `git commit -m "..."`
    try:
        git_cmd = find_git_commit_cmdline()
        msg = ""
        for i, arg in enumerate(git_cmd):
            if arg == "-m" and i + 1 < len(git_cmd):
                msg = git_cmd[i + 1]
                break
            elif arg.startswith("-m"):
                msg = arg[2:]
                break

        if msg:
            if "[major]" in msg or "BREAKING CHANGE" in msg or re.search(r"^[a-z]+(\([^\)]+\))?!:", msg):
                return "major"
            if "[minor]" in msg or re.match(r"^feat(\([^\)]+\))?:", msg):
                return "minor"
            if "[patch]" in msg:
                return "patch"
            if "[no-bump]" in msg or "[skip-version]" in msg:
                return "none"
    except Exception:
        pass

    # 3. Check current git branch name (e.g. feat/..., feature/...)
    try:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False).lower()
        if branch.startswith("feat/") or branch.startswith("feature/"):
            return "minor"
        if branch.startswith("fix/") or branch.startswith("bugfix/"):
            return "patch"
    except Exception:
        pass

    return "patch"


def is_code_file_changed(filepath: str) -> bool:
    """Check whether a filepath represents application/build source code."""
    path = Path(filepath)
    if path.suffix in CODE_EXTENSIONS:
        return True
    for part in path.parts:
        if part in CODE_DIRECTORIES:
            return True
    return False


def pre_commit_hook():
    """
    Called by Git pre-commit hook.
    Checks staged files: if code files are staged and info.py wasn't manually touched,
    automatically bumps the version (minor for feat, patch for fix/other) and stages info.py.
    """
    if os.environ.get("OPTOLITHIUM_NO_BUMP") == "1":
        return 0

    try:
        # Get list of staged files
        staged_files = run_git(["diff", "--cached", "--name-only"], check=False).splitlines()
    except Exception:
        return 0

    if not staged_files:
        return 0

    # If info.py was already manually staged, respect the manual bump
    if "OptolithiumGui/info.py" in staged_files:
        return 0

    # Check if any actual code files were changed
    code_changed = any(is_code_file_changed(f) for f in staged_files)
    if not code_changed:
        return 0

    bump_type = detect_bump_from_cmdline_or_env()
    if bump_type == "none":
        return 0

    current = read_current_version()
    new_version = calculate_bump(current, bump_type)

    # Sync to files
    sync_version_to_files(new_version)

    # Stage the updated version files into the current commit
    files_to_stage = ["OptolithiumGui/info.py"]
    if AIP_FILE.exists():
        files_to_stage.append("installer/Optolithium.aip")
    if SPEC_FILE.exists():
        files_to_stage.append("packaging/optolithium.spec")

    run_git(["add"] + files_to_stage, check=False)
    print(f"[version-control] Automated version bump: {current} -> {new_version} ({bump_type})")
    return 0


def install_git_hook():
    """Install the pre-commit hook in .githooks and configure core.hooksPath."""
    GITHOOKS_DIR.mkdir(parents=True, exist_ok=True)
    
    hook_content = """#!/usr/bin/env bash
# Auto-generated by Optolithium Version Manager
exec python3 "$(git rev-parse --show-toplevel)/tools/version_manager.py" hook pre-commit
"""
    GIT_HOOK_PRE_COMMIT.write_text(hook_content, encoding="utf-8")
    GIT_HOOK_PRE_COMMIT.chmod(0o755)

    # Also install to .git/hooks as fallback
    git_dir_hooks = REPO_ROOT / ".git" / "hooks"
    if git_dir_hooks.exists():
        try:
            local_hook = git_dir_hooks / "pre-commit"
            local_hook.write_text(hook_content, encoding="utf-8")
            local_hook.chmod(0o755)
        except OSError:
            pass

    # Configure git to use .githooks directory
    run_git(["config", "core.hooksPath", ".githooks"], check=False)
    print("Git pre-commit version hook installed successfully.")
    print("Every commit with code changes will automatically bump the minor or patch version.")


def uninstall_git_hook():
    """Uninstall the versioning git hook."""
    if GIT_HOOK_PRE_COMMIT.exists():
        GIT_HOOK_PRE_COMMIT.unlink()
    run_git(["config", "--unset", "core.hooksPath"], check=False)
    print("Git pre-commit version hook uninstalled.")


def main():
    parser = argparse.ArgumentParser(
        description="Optolithium Automated Semantic Version Manager (SemVer)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  version_manager.py get             # Print current version (e.g. 0.3.0)
  version_manager.py status          # Detailed version and git status
  version_manager.py bump patch      # Bump 0.3.0 -> 0.3.1
  version_manager.py bump minor      # Bump 0.3.0 -> 0.4.0
  version_manager.py bump major      # Bump 0.3.0 -> 1.0.0
  version_manager.py auto            # Auto-bump from git commit history
  version_manager.py set 0.4.0       # Set explicit version
  version_manager.py install-hook    # Activate automated Git pre-commit version bumping
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # get
    get_parser = subparsers.add_parser("get", help="Get current version")
    get_parser.add_argument("--json", action="store_true", help="Output details as JSON")

    # status
    subparsers.add_parser("status", help="Show version and repository git status")

    # bump
    bump_parser = subparsers.add_parser("bump", help="Bump version by component")
    bump_parser.add_argument("type", choices=["patch", "minor", "major"], help="Component to bump")
    bump_parser.add_argument("--stage", "-s", action="store_true", help="Stage modified files in git")
    bump_parser.add_argument("--commit", "-c", action="store_true", help="Commit version bump in git")
    bump_parser.add_argument("--tag", "-t", action="store_true", help="Create git tag for new version")

    # auto
    auto_parser = subparsers.add_parser("auto", help="Auto-detect bump from git history (feat->minor, fix->patch)")
    auto_parser.add_argument("--stage", "-s", action="store_true", help="Stage modified files in git")
    auto_parser.add_argument("--commit", "-c", action="store_true", help="Commit version bump in git")
    auto_parser.add_argument("--tag", "-t", action="store_true", help="Create git tag for new version")

    # set
    set_parser = subparsers.add_parser("set", help="Set specific version")
    set_parser.add_argument("version", help="New version string (e.g. 0.4.0)")
    set_parser.add_argument("--stage", "-s", action="store_true", help="Stage modified files in git")
    set_parser.add_argument("--commit", "-c", action="store_true", help="Commit version bump in git")
    set_parser.add_argument("--tag", "-t", action="store_true", help="Create git tag for new version")

    # tag
    subparsers.add_parser("tag", help="Create git tag for current version")

    # hook
    hook_parser = subparsers.add_parser("hook", help="Git hook trigger")
    hook_parser.add_argument("hook_name", choices=["pre-commit"], help="Hook name")

    # install-hook / uninstall-hook
    subparsers.add_parser("install-hook", help="Install automated Git pre-commit hook")
    subparsers.add_parser("uninstall-hook", help="Uninstall automated Git hook")

    args = parser.parse_args()

    if not args.command or args.command == "get":
        current = read_current_version()
        if getattr(args, "json", False):
            info = get_git_info()
            major, minor, patch, prerelease = parse_semver(current)
            output = {
                "version": current,
                "major": major,
                "minor": minor,
                "patch": patch,
                "prerelease": prerelease,
                "git": info
            }
            print(json.dumps(output, indent=2))
        else:
            print(current)
        return

    if args.command == "status":
        current = read_current_version()
        info = get_git_info()
        print("==================================================")
        print(" Optolithium Version Status")
        print("==================================================")
        print(f" Master Version:       {current}")
        print(f" Git Branch:           {info['branch']}")
        print(f" Current Commit:       {info['commit']}")
        print(f" Git Describe:         {info['describe']}")
        print(f" Working Tree Dirty:   {info['is_dirty']}")
        print(f" Commits Since Bump:   {info['commits_since_last_bump']}")
        detected = detect_bump_type_from_commits()
        next_ver = calculate_bump(current, detected)
        print(f" Next Auto Version:    {next_ver} ({detected})")
        print("==================================================")
        return

    if args.command == "bump":
        current = read_current_version()
        new_version = calculate_bump(current, args.type)
        sync_version_to_files(new_version)
        print(f"Version bumped from {current} -> {new_version} ({args.type})")
        if args.stage or args.commit:
            run_git(["add", "OptolithiumGui/info.py", "installer/Optolithium.aip", "packaging/optolithium.spec"], check=False)
        if args.commit:
            run_git(["commit", "-m", f"chore(release): bump version to {new_version}"], check=False)
            print(f"Committed: chore(release): bump version to {new_version}")
        if args.tag:
            run_git(["tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=False)
            print(f"Created git tag: v{new_version}")
        return

    if args.command == "auto":
        current = read_current_version()
        bump_type = detect_bump_type_from_commits()
        new_version = calculate_bump(current, bump_type)
        sync_version_to_files(new_version)
        print(f"Auto-bumped version: {current} -> {new_version} ({bump_type}) based on git commit history")
        if args.stage or args.commit:
            run_git(["add", "OptolithiumGui/info.py", "installer/Optolithium.aip", "packaging/optolithium.spec"], check=False)
        if args.commit:
            run_git(["commit", "-m", f"chore(release): bump version to {new_version}"], check=False)
            print(f"Committed: chore(release): bump version to {new_version}")
        if args.tag:
            run_git(["tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"], check=False)
            print(f"Created git tag: v{new_version}")
        return

    if args.command == "set":
        parse_semver(args.version)  # Validate format
        current = read_current_version()
        sync_version_to_files(args.version)
        print(f"Version set: {current} -> {args.version}")
        if args.stage or args.commit:
            run_git(["add", "OptolithiumGui/info.py", "installer/Optolithium.aip", "packaging/optolithium.spec"], check=False)
        if args.commit:
            run_git(["commit", "-m", f"chore(release): set version to {args.version}"], check=False)
            print(f"Committed: chore(release): set version to {args.version}")
        if args.tag:
            run_git(["tag", "-a", f"v{args.version}", "-m", f"Release v{args.version}"], check=False)
            print(f"Created git tag: v{args.version}")
        return

    if args.command == "tag":
        current = read_current_version()
        run_git(["tag", "-a", f"v{current}", "-m", f"Release v{current}"], check=False)
        print(f"Created git tag: v{current}")
        return

    if args.command == "hook":
        if args.hook_name == "pre-commit":
            sys.exit(pre_commit_hook())
        return

    if args.command == "install-hook":
        install_git_hook()
        return

    if args.command == "uninstall-hook":
        uninstall_git_hook()
        return


if __name__ == "__main__":
    main()
