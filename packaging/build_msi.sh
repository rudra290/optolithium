#!/usr/bin/env bash
# ==============================================================================
# Script to prepare and build Windows .msi Installer for Optolithium
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_DIR/dist/msi"
STAGING_DIR="$REPO_DIR/dist/msi-staging"
VERSION=""

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --output-dir DIR   Directory to output .msi installer (default: dist/msi)
  --staging-dir DIR  Directory for staging MSI build files (default: dist/msi-staging)
  --version VER      Override package version (default: from OptolithiumGui/info.py)
  -h, --help         Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --staging-dir)
            STAGING_DIR="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
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

if [ -z "$VERSION" ]; then
    VERSION="$(grep -E '__version__\s*=' "$REPO_DIR/OptolithiumGui/info.py" | head -n1 | cut -d'"' -f2)"
    if [ -z "$VERSION" ]; then
        VERSION="0.3.0"
    fi
fi

MSI_NAME="optolithium-${VERSION}.msi"

echo "=========================================================="
echo " Preparing Optolithium Windows MSI Package"
echo " Version:      $VERSION"
echo " Staging Dir:  $STAGING_DIR"
echo " Output Dir:   $OUTPUT_DIR"
echo " Target MSI:   $MSI_NAME"
echo "=========================================================="

# Prepare staging directories
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/app"
mkdir -p "$OUTPUT_DIR"

# 1. Copy application files into staging/app
echo "==> Staging application files..."
rsync -a \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="logs" \
    --exclude="icons_sources" \
    --exclude=".vscode" \
    --exclude=".venv" \
    "$REPO_DIR/OptolithiumGui/" "$STAGING_DIR/app/"

# 2. Add Windows launchers
echo "==> Creating Windows launchers..."
cat << 'EOF' > "$STAGING_DIR/optolithium.bat"
@echo off
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%app"
set "PYTHONPATH=%APP_DIR%;%PYTHONPATH%"

:: 1. Check for bundled/embedded Python runtime
if exist "%SCRIPT_DIR%python\pythonw.exe" (
    start "" "%SCRIPT_DIR%python\pythonw.exe" "%APP_DIR%\main.py" %*
) else if exist "%SCRIPT_DIR%venv\Scripts\pythonw.exe" (
    start "" "%SCRIPT_DIR%venv\Scripts\pythonw.exe" "%APP_DIR%\main.py" %*
) else (
    start "" pythonw "%APP_DIR%\main.py" %*
)
EOF

cat << 'EOF' > "$STAGING_DIR/optolithium-cli.bat"
@echo off
set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%app"
set "PYTHONPATH=%APP_DIR%;%PYTHONPATH%"

if exist "%SCRIPT_DIR%python\python.exe" (
    "%SCRIPT_DIR%python\python.exe" "%APP_DIR%\main.py" %*
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    "%SCRIPT_DIR%venv\Scripts\python.exe" "%APP_DIR%\main.py" %*
) else (
    python "%APP_DIR%\main.py" %*
)
EOF

# 3. Copy application icon
ICON_SRC="$REPO_DIR/OptolithiumGui/icon.ico"
if [ -f "$ICON_SRC" ]; then
    cp -f "$ICON_SRC" "$STAGING_DIR/icon.ico"
fi

# 4. Generate WiX specification (.wxs)
WXS_PATH="$STAGING_DIR/optolithium.wxs"
echo "==> Generating WiX specification ($WXS_PATH)..."
python3 "$REPO_DIR/packaging/generate_wxs.py" \
    --staging-dir "$STAGING_DIR" \
    --version "$VERSION" \
    --output "$WXS_PATH"

# 5. Generate Windows build scripts for WiX
cat << EOF > "$STAGING_DIR/build_msi.bat"
@echo off
echo ========================================================
echo Building Optolithium MSI with WiX Toolset v3
echo ========================================================
where candle.exe >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: WiX Toolset 'candle.exe' was not found in PATH.
    echo Please install WiX Toolset v3 from https://wixtoolset.org/
    pause
    exit /b 1
)

candle.exe -nologo optolithium.wxs -out optolithium.wixobj
light.exe -nologo -sval optolithium.wixobj -out %MSI_NAME%
echo MSI package built successfully: %MSI_NAME%
pause
EOF

cat << EOF > "$STAGING_DIR/build_msi_v4.bat"
@echo off
echo ========================================================
echo Building Optolithium MSI with WiX Toolset v4/v5
echo ========================================================
where wix.exe >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: 'wix.exe' was not found in PATH.
    echo Install it using: dotnet tool install --global wix
    pause
    exit /b 1
)

wix build optolithium.wxs -o %MSI_NAME%
echo MSI package built successfully: %MSI_NAME%
pause
EOF

cat << EOF > "$STAGING_DIR/build_msi.ps1"
# PowerShell WiX Builder
Write-Host "Building Optolithium MSI Package..." -ForegroundColor Cyan
if (Get-Command "wix" -ErrorAction SilentlyContinue) {
    wix build optolithium.wxs -o "$MSI_NAME"
    Write-Host "Success! Created: $MSI_NAME" -ForegroundColor Green
} elseif (Get-Command "candle" -ErrorAction SilentlyContinue) {
    candle -nologo optolithium.wxs -out optolithium.wixobj
    light -nologo -sval optolithium.wixobj -out "$MSI_NAME"
    Write-Host "Success! Created: $MSI_NAME" -ForegroundColor Green
} else {
    Write-Host "Neither WiX v4 (wix.exe) nor WiX v3 (candle.exe) was found in PATH." -ForegroundColor Yellow
    Write-Host "Install WiX using: dotnet tool install --global wix"
}
EOF

# 6. Check for WiX compiler: bundled wixl, system wixl, or Windows wix
WIXL_BIN=""
if [ -x "$REPO_DIR/packaging/tools/wixl" ]; then
    WIXL_BIN="$REPO_DIR/packaging/tools/wixl"
elif command -v wixl >/dev/null 2>&1; then
    WIXL_BIN="$(command -v wixl)"
fi

if [ -n "$WIXL_BIN" ]; then
    echo "==> Native WiX compiler 'wixl' detected ($WIXL_BIN). Compiling MSI..."
    (cd "$STAGING_DIR" && "$WIXL_BIN" -v -o "$OUTPUT_DIR/$MSI_NAME" optolithium.wxs)
    echo "=========================================================="
    echo " MSI Build Complete!"
    echo " Package generated: $OUTPUT_DIR/$MSI_NAME"
    ls -lh "$OUTPUT_DIR/$MSI_NAME"
    echo "=========================================================="
else
    echo "=========================================================="
    echo " MSI Staging & WiX Specification Complete!"
    echo " Staging Location: $STAGING_DIR"
    echo " WiX Source:       $WXS_PATH"
    echo "=========================================================="
    echo ""
    echo "How to compile this into .msi:"
    echo ""
    echo "1. DIRECTLY ON LINUX (via msitools):"
    echo "   Install msitools package:"
    echo "       sudo dnf install -y msitools    # Fedora / RHEL / Rocky Linux"
    echo "       sudo apt install -y msitools    # Ubuntu / Debian"
    echo "   Then re-run:"
    echo "       ./packaging/build_msi.sh"
    echo ""
    echo "2. ON WINDOWS (using WiX Toolset):"
    echo "   Copy '$STAGING_DIR' to a Windows machine and run either:"
    echo "       .\\build_msi.bat       (WiX Toolset v3)"
    echo "       .\\build_msi_v4.bat    (WiX Toolset v4/v5 dotnet tool)"
    echo "=========================================================="
fi

