#!/usr/bin/env bash
# ==============================================================================
# Script to create DNF repository and .repo file for Optolithium
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RPM_SOURCE_DIR="$REPO_DIR/dist/rpm"
DNF_REPO_DIR="$REPO_DIR/dist/dnf-repo"
REPO_ID="optolithium-local"
CUSTOM_BASEURL=""

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --rpm-dir DIR      Directory containing .rpm packages (default: dist/rpm)
  --repo-dir DIR     Destination directory for DNF repository (default: dist/dnf-repo)
  --baseurl URL      Custom baseurl for .repo file (default: file://<absolute repo-dir>)
  -h, --help         Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rpm-dir)
            RPM_SOURCE_DIR="$2"
            shift 2
            ;;
        --repo-dir)
            DNF_REPO_DIR="$2"
            shift 2
            ;;
        --baseurl)
            CUSTOM_BASEURL="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            print_usage
            exit 1
            ;;
    esac
done

echo "=========================================================="
echo " Creating DNF Repository for Optolithium"
echo " Source RPM Dir:  $RPM_SOURCE_DIR"
echo " DNF Repo Dir:    $DNF_REPO_DIR"
echo "=========================================================="

# Check if RPM packages exist
if [ ! -d "$RPM_SOURCE_DIR" ] || [ -z "$(find "$RPM_SOURCE_DIR" -name "*.rpm" 2>/dev/null)" ]; then
    echo "No .rpm packages found in $RPM_SOURCE_DIR."
    echo "Running build_rpm.sh first..."
    bash "$REPO_DIR/packaging/build_rpm.sh" --output-dir "$RPM_SOURCE_DIR"
fi

mkdir -p "$DNF_REPO_DIR"

# Copy RPM packages into DNF repo directory
echo "==> Copying RPM packages to $DNF_REPO_DIR..."
cp -f "$RPM_SOURCE_DIR"/*.rpm "$DNF_REPO_DIR/"

# Determine absolute path for repo
ABS_REPO_DIR="$(cd "$DNF_REPO_DIR" && pwd)"
BASE_URL="${CUSTOM_BASEURL:-file://$ABS_REPO_DIR}"

# Run createrepo_c or createrepo if available
if command -v createrepo_c >/dev/null 2>&1; then
    echo "==> Generating repository metadata using createrepo_c..."
    createrepo_c --update "$DNF_REPO_DIR"
elif command -v createrepo >/dev/null 2>&1; then
    echo "==> Generating repository metadata using createrepo..."
    createrepo --update "$DNF_REPO_DIR"
else
    echo "==> [Notice] 'createrepo_c' is not currently installed on this system."
    echo "    To generate repository metadata (repodata/), install it via:"
    echo "        sudo dnf install -y createrepo_c"
    echo "    Then re-run: ./packaging/create_dnf_repo.sh"
    echo "    (Note: You can still install the RPM directly with: sudo dnf install $RPM_SOURCE_DIR/*.rpm)"
fi

# Generate DNF .repo file
REPO_FILE="$DNF_REPO_DIR/optolithium.repo"
echo "==> Generating DNF repository configuration: $REPO_FILE..."
cat << EOF > "$REPO_FILE"
# Optolithium DNF / YUM Repository Configuration
# Place this file in /etc/yum.repos.d/ to enable installation via DNF

[$REPO_ID]
name=Optolithium Repository
baseurl=$BASE_URL
enabled=1
gpgcheck=0
priority=1
EOF

# Also generate a template for remote HTTP hosting
REMOTE_REPO_FILE="$DNF_REPO_DIR/optolithium-remote.repo.template"
cat << 'EOF' > "$REMOTE_REPO_FILE"
# Optolithium Remote DNF Repository Template
# Replace https://your-server.org/repos/ with your actual hosting URL

[optolithium-remote]
name=Optolithium Remote Repository
baseurl=https://your-server.org/repos/el$releasever/$basearch/
enabled=1
gpgcheck=0
metadata_expire=1h
EOF

# Copy .repo file to dist root as well for convenience
cp -f "$REPO_FILE" "$REPO_DIR/dist/optolithium.repo"

echo "=========================================================="
echo " DNF Repository Generation Finished!"
echo " Repository Location: $ABS_REPO_DIR"
echo " DNF .repo file:      $REPO_FILE"
echo "=========================================================="
echo "Installation Options with DNF:"
echo ""
echo "1. Direct RPM Installation (Fastest, does not require a repo):"
echo "   sudo dnf install $(ls -1 "$DNF_REPO_DIR"/*.rpm | head -n1)"
echo ""
echo "2. Add the DNF Repository Configuration:"
echo "   sudo cp \"$REPO_FILE\" /etc/yum.repos.d/"
echo "   sudo dnf makecache"
echo "   sudo dnf install optolithium"
echo ""
echo "3. One-off installation using --repofrompath:"
echo "   sudo dnf --repofrompath=optolithium,\"$ABS_REPO_DIR\" --nogpgcheck install optolithium"
echo "=========================================================="

