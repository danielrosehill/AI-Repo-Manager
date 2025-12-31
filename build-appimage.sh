#!/bin/bash
set -e

# Build script for AI Repo Manager AppImage
# User data in ~/.config/ai-repo-manager and ~/.local/share/ai-repo-manager
# is preserved during install/upgrade/removal

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Package info
PKG_NAME="ai-repo-manager"
VERSION=$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2)
BUILD_DIR="build/appimage-build"
OUTPUT_DIR="dist"
APPDIR="$BUILD_DIR/AI_Repo_Manager.AppDir"

echo "=========================================="
echo "Building $PKG_NAME AppImage version $VERSION"
echo "=========================================="

# Check for appimagetool
APPIMAGETOOL=""
if [ -f "./appimagetool-x86_64.AppImage" ]; then
    APPIMAGETOOL="./appimagetool-x86_64.AppImage"
elif command -v appimagetool &> /dev/null; then
    APPIMAGETOOL="appimagetool"
else
    echo "Error: appimagetool not found."
    echo "Download it from: https://github.com/AppImage/AppImageKit/releases"
    echo "  wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    echo "  chmod +x appimagetool-x86_64.AppImage"
    exit 1
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$APPDIR"

# Create AppDir structure
echo "Creating AppDir structure..."
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib/python3"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"

# Create virtual environment
echo "Creating Python virtual environment..."
if command -v uv &> /dev/null; then
    uv venv "$APPDIR/usr"
    uv pip install --python "$APPDIR/usr/bin/python" .
else
    python3 -m venv "$APPDIR/usr"
    "$APPDIR/usr/bin/pip" install --upgrade pip --quiet
    "$APPDIR/usr/bin/pip" install . --quiet
fi

# Copy application source
echo "Copying application files..."
cp -r src "$APPDIR/usr/lib/python3/"
cp -r icons "$APPDIR/usr/lib/python3/"
cp pyproject.toml "$APPDIR/usr/lib/python3/"

# Create AppRun script
echo "Creating AppRun script..."
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

# Set up Python environment
export PATH="$HERE/usr/bin:$PATH"
export PYTHONHOME="$HERE/usr"
export PYTHONPATH="$HERE/usr/lib/python3:$PYTHONPATH"

# Ensure user data directories exist
mkdir -p "$HOME/.config/ai-repo-manager"
mkdir -p "$HOME/.local/share/ai-repo-manager"

# Run the application
cd "$HERE/usr/lib/python3"
exec "$HERE/usr/bin/python3" -m src.main "$@"
EOF
chmod +x "$APPDIR/AppRun"

# Copy desktop file
echo "Installing desktop integration..."
cat > "$APPDIR/ai-repo-manager.desktop" << EOF
[Desktop Entry]
Name=AI Repo Manager
Comment=Manage GitHub repositories with semantic search
Exec=ai-repo-manager
Icon=ai-repo-manager
Terminal=false
Type=Application
Categories=Development;Utility;
Keywords=github;repository;git;semantic;search;ai;
StartupWMClass=ai-repo-manager
X-AppImage-Version=$VERSION
EOF
cp "$APPDIR/ai-repo-manager.desktop" "$APPDIR/usr/share/applications/"

# Copy icon
cp debian/ai-repo-manager.svg "$APPDIR/ai-repo-manager.svg"
cp debian/ai-repo-manager.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cp debian/ai-repo-manager.svg "$APPDIR/.DirIcon"

# Create PNG icon for better compatibility
if command -v convert &> /dev/null; then
    convert -background none debian/ai-repo-manager.svg -resize 256x256 "$APPDIR/ai-repo-manager.png"
fi

# Build AppImage
echo "Building AppImage..."
ARCH=x86_64 $APPIMAGETOOL "$APPDIR" "$OUTPUT_DIR/AI_Repo_Manager-${VERSION}-x86_64.AppImage"

# Show results
echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo "AppImage: $OUTPUT_DIR/AI_Repo_Manager-${VERSION}-x86_64.AppImage"
echo ""
echo "Run with:"
echo "  chmod +x $OUTPUT_DIR/AI_Repo_Manager-${VERSION}-x86_64.AppImage"
echo "  ./$OUTPUT_DIR/AI_Repo_Manager-${VERSION}-x86_64.AppImage"
echo ""
echo "Your existing data will be preserved:"
echo "  - Settings: ~/.config/ai-repo-manager/"
echo "  - Vector Store: ~/.local/share/ai-repo-manager/"
echo ""
ls -lh "$OUTPUT_DIR/AI_Repo_Manager-${VERSION}-x86_64.AppImage"
