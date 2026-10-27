#!/usr/bin/env bash
# ==============================================================================
# Script to create APT repository for Optolithium (.deb packages)
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_SOURCE_DIR="$REPO_DIR/dist/deb"
APT_REPO_DIR="$REPO_DIR/dist/apt-repo"
CUSTOM_BASEURL=""

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --deb-dir DIR      Directory containing .deb packages (default: dist/deb)
  --repo-dir DIR     Destination directory for APT repository (default: dist/apt-repo)
  --baseurl URL      Custom baseurl for APT sources (default: file://<absolute repo-dir>)
  -h, --help         Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --deb-dir)
            DEB_SOURCE_DIR="$2"
            shift 2
            ;;
        --repo-dir)
            APT_REPO_DIR="$2"
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
echo " Creating APT Repository for Optolithium"
echo " Source DEB Dir:  $DEB_SOURCE_DIR"
echo " APT Repo Dir:    $APT_REPO_DIR"
echo "=========================================================="

# Check if DEB packages exist
if [ ! -d "$DEB_SOURCE_DIR" ] || [ -z "$(find "$DEB_SOURCE_DIR" -name "*.deb" 2>/dev/null)" ]; then
    echo "No .deb packages found in $DEB_SOURCE_DIR."
    echo "Running build_deb.sh first..."
    bash "$REPO_DIR/packaging/build_deb.sh" --output-dir "$DEB_SOURCE_DIR"
fi

mkdir -p "$APT_REPO_DIR"

# Copy DEB packages into APT repo directory
echo "==> Copying DEB packages to $APT_REPO_DIR..."
cp -f "$DEB_SOURCE_DIR"/*.deb "$APT_REPO_DIR/"

ABS_REPO_DIR="$(cd "$APT_REPO_DIR" && pwd)"
BASE_URL="${CUSTOM_BASEURL:-file://$ABS_REPO_DIR}"

# Generate Packages file
echo "==> Generating Packages index..."
PACKAGES_FILE="$APT_REPO_DIR/Packages"
rm -f "$PACKAGES_FILE" "$PACKAGES_FILE.gz"

if command -v dpkg-scanpackages >/dev/null 2>&1; then
    (cd "$APT_REPO_DIR" && dpkg-scanpackages . /dev/null > Packages)
else
    # Portable Python fallback to generate Packages file
    python3 - << 'EOF' "$APT_REPO_DIR"
import sys, os, hashlib, subprocess

repo_dir = sys.argv[1]
packages_file = os.path.join(repo_dir, "Packages")

with open(packages_file, "w") as out_f:
    for fname in sorted(os.listdir(repo_dir)):
        if not fname.endswith(".deb"):
            continue
        deb_path = os.path.join(repo_dir, fname)
        size = os.path.getsize(deb_path)

        with open(deb_path, "rb") as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()
            sha256 = hashlib.sha256(data).hexdigest()

        # Extract control information using ar + tar
        p1 = subprocess.Popen(["ar", "-p", deb_path, "control.tar.gz"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["tar", "-zx", "-O", "./control"], stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        control_bytes, _ = p2.communicate()
        control_text = control_bytes.decode("utf-8", errors="replace").strip()

        out_f.write(control_text + "\n")
        out_f.write(f"Filename: {fname}\n")
        out_f.write(f"Size: {size}\n")
        out_f.write(f"MD5sum: {md5}\n")
        out_f.write(f"SHA256: {sha256}\n\n")

print("==> Packages index successfully generated.")
EOF
fi

gzip -9c "$PACKAGES_FILE" > "$PACKAGES_FILE.gz"

# Generate Release file
cat << EOF > "$APT_REPO_DIR/Release"
Archive: stable
Component: main
Origin: Optolithium
Label: Optolithium Repository
Architecture: amd64
Date: $(date -Ru 2>/dev/null || date)
EOF

# Generate traditional .list file (for /etc/apt/sources.list.d/optolithium.list)
LIST_FILE="$APT_REPO_DIR/optolithium.list"
echo "deb [trusted=yes] $BASE_URL ./" > "$LIST_FILE"
cp -f "$LIST_FILE" "$REPO_DIR/dist/optolithium.list"

# Generate modern DEB822 .sources file (for /etc/apt/sources.list.d/optolithium.sources)
SOURCES_FILE="$APT_REPO_DIR/optolithium.sources"
cat << EOF > "$SOURCES_FILE"
Types: deb
URIs: $BASE_URL
Suites: ./
Trusted: yes
EOF
cp -f "$SOURCES_FILE" "$REPO_DIR/dist/optolithium.sources"

echo "=========================================================="
echo " APT Repository Generation Finished!"
echo " Repository Location: $ABS_REPO_DIR"
echo " APT .list file:      $LIST_FILE"
echo " APT .sources file:   $SOURCES_FILE"
echo "=========================================================="
echo "Installation Options with APT on Ubuntu/Debian:"
echo ""
echo "1. Direct DEB Installation (Fastest, does not require a repo):"
echo "   sudo apt install $(ls -1 "$APT_REPO_DIR"/*.deb | head -n1)"
echo ""
echo "2. Add the APT Repository Configuration:"
echo "   sudo cp \"$LIST_FILE\" /etc/apt/sources.list.d/"
echo "   sudo apt update"
echo "   sudo apt install optolithium"
echo "=========================================================="

