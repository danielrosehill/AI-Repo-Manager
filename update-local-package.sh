#!/bin/bash
set -e

# Update local package script for AI Repo Manager
# Builds and installs the latest version of the Debian package

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Updating AI Repo Manager local package"
echo "=========================================="

# Build the package
echo "Building package..."
./build-deb.sh

# Get version from pyproject.toml
VERSION=$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2)
PKG_FILE="dist/ai-repo-manager_${VERSION}_all.deb"

if [ ! -f "$PKG_FILE" ]; then
    echo "Error: Package file not found: $PKG_FILE"
    exit 1
fi

# Install the package
echo ""
echo "Installing package..."
sudo dpkg -i "$PKG_FILE"

echo ""
echo "=========================================="
echo "Update complete!"
echo "=========================================="
echo "Version: $VERSION"
echo ""
echo "Run with: ai-repo-manager"
