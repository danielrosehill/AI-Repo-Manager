#!/bin/bash
set -e

# Build script for AI Repo Manager Debian package
# User data in ~/.config/ai-repo-manager and ~/.local/share/ai-repo-manager
# is preserved during install/upgrade/removal

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Package info
PKG_NAME="ai-repo-manager"
VERSION=$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2)
BUILD_DIR="build/deb-build"
OUTPUT_DIR="dist"

echo "=========================================="
echo "Building $PKG_NAME version $VERSION"
echo "=========================================="

# Check dependencies
echo "Checking build dependencies..."
for cmd in dpkg-deb python3; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$OUTPUT_DIR"

# Create package structure
PKG_ROOT="$BUILD_DIR/${PKG_NAME}_${VERSION}_all"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/opt/$PKG_NAME"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps"

# Create virtual environment in package
echo "Creating Python virtual environment..."
if command -v uv &> /dev/null; then
    uv venv "$PKG_ROOT/opt/$PKG_NAME/venv"
    uv pip install --python "$PKG_ROOT/opt/$PKG_NAME/venv/bin/python" .
else
    python3 -m venv "$PKG_ROOT/opt/$PKG_NAME/venv"
    "$PKG_ROOT/opt/$PKG_NAME/venv/bin/pip" install --upgrade pip --quiet
    "$PKG_ROOT/opt/$PKG_NAME/venv/bin/pip" install . --quiet
fi

# Copy application source
echo "Copying application files..."
cp -r src "$PKG_ROOT/opt/$PKG_NAME/"
cp pyproject.toml "$PKG_ROOT/opt/$PKG_NAME/"
cp README.md "$PKG_ROOT/opt/$PKG_NAME/" 2>/dev/null || true

# Create launcher script
echo "Creating launcher script..."
cat > "$PKG_ROOT/usr/bin/$PKG_NAME" << 'EOF'
#!/bin/bash
# AI Repo Manager launcher
# User data is preserved in:
#   - ~/.config/ai-repo-manager/ (settings)
#   - ~/.local/share/ai-repo-manager/ (vector database)

exec /opt/ai-repo-manager/venv/bin/python -m src.main "$@"
EOF
chmod 755 "$PKG_ROOT/usr/bin/$PKG_NAME"

# Copy desktop file and icon
echo "Installing desktop integration..."
cp debian/ai-repo-manager.desktop "$PKG_ROOT/usr/share/applications/"
cp debian/ai-repo-manager.svg "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/"

# Create DEBIAN/control
echo "Creating package metadata..."
cat > "$PKG_ROOT/DEBIAN/control" << EOF
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.11)
Maintainer: Daniel Rosehill <public@danielrosehill.com>
Homepage: https://github.com/danielrosehill/AI-Repo-Manager
Description: GitHub repository manager with semantic search
 A Linux desktop application for managing GitHub repositories with
 semantic search powered by OpenRouter embeddings and ChromaDB.
 .
 Features include:
  - Repository Management: View all your GitHub repositories
  - Semantic Search: Find repositories using natural language
  - AI Chat: Ask questions about your repositories using RAG
  - Local Detection: Automatically detects locally cloned repos
  - Quick Actions: Open in VS Code, view on GitHub, or delete
 .
 User data is stored in:
  - Settings: ~/.config/ai-repo-manager/
  - Vector Store: ~/.local/share/ai-repo-manager/
EOF

# Create postinst script to update icon cache
cat > "$PKG_ROOT/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
if [ -x /usr/bin/update-icon-caches ]; then
    /usr/bin/update-icon-caches /usr/share/icons/hicolor || true
fi
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database /usr/share/applications || true
fi
EOF
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

# Create postrm script for cleanup (but preserve user data)
cat > "$PKG_ROOT/DEBIAN/postrm" << 'EOF'
#!/bin/bash
set -e
if [ "$1" = "purge" ]; then
    # Note: User data in ~/.config and ~/.local is NOT removed
    # This is intentional to preserve settings and vector database
    echo "Note: User data in ~/.config/ai-repo-manager and ~/.local/share/ai-repo-manager is preserved."
    echo "Remove manually if no longer needed."
fi
if [ -x /usr/bin/update-icon-caches ]; then
    /usr/bin/update-icon-caches /usr/share/icons/hicolor || true
fi
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database /usr/share/applications || true
fi
EOF
chmod 755 "$PKG_ROOT/DEBIAN/postrm"

# Set permissions
echo "Setting permissions..."
find "$PKG_ROOT" -type d -exec chmod 755 {} \;
find "$PKG_ROOT/opt" -type f -exec chmod 644 {} \;
find "$PKG_ROOT/opt/$PKG_NAME/venv/bin" -type f -exec chmod 755 {} \;
chmod 755 "$PKG_ROOT/usr/bin/$PKG_NAME"
# Ensure desktop file and icon are world-readable
chmod 644 "$PKG_ROOT/usr/share/applications/"*.desktop
chmod 644 "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/"*.svg

# Build the package
echo "Building Debian package..."
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUTPUT_DIR/${PKG_NAME}_${VERSION}_all.deb"

# Show results
echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo "Package: $OUTPUT_DIR/${PKG_NAME}_${VERSION}_all.deb"
echo ""
echo "Install with:"
echo "  sudo dpkg -i $OUTPUT_DIR/${PKG_NAME}_${VERSION}_all.deb"
echo ""
echo "Your existing data will be preserved:"
echo "  - Settings: ~/.config/ai-repo-manager/"
echo "  - Vector Store: ~/.local/share/ai-repo-manager/"
echo ""
ls -lh "$OUTPUT_DIR/${PKG_NAME}_${VERSION}_all.deb"
