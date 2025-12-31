#!/bin/bash
set -e

# Unified release script for AI Repo Manager
# Does everything: bump version, build deb, install locally, commit, tag, push to GitHub
#
# Usage:
#   ./release.sh          # Interactive menu
#   ./release.sh patch    # Auto bump patch (1.0.0 -> 1.0.1)
#   ./release.sh minor    # Auto bump minor (1.0.0 -> 1.1.0)
#   ./release.sh major    # Auto bump major (1.0.0 -> 2.0.0)
#   ./release.sh 1.2.3    # Set specific version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Get current version
CURRENT_VERSION=$(grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2)
echo "Current version: $CURRENT_VERSION"

# Parse current version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR="${VERSION_PARTS[0]}"
MINOR="${VERSION_PARTS[1]}"
PATCH="${VERSION_PARTS[2]}"

# Determine new version based on argument
if [ -z "$1" ]; then
    # Interactive menu
    echo ""
    echo "Release type:"
    echo "  1) Patch  ($MAJOR.$MINOR.$((PATCH + 1)))"
    echo "  2) Minor  ($MAJOR.$((MINOR + 1)).0)"
    echo "  3) Major  ($((MAJOR + 1)).0.0)"
    echo "  4) Custom version"
    echo ""
    read -p "Select [1-4]: " -n 1 -r CHOICE
    echo ""

    case $CHOICE in
        1) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
        2) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
        3) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
        4)
            read -p "Enter version: " NEW_VERSION
            ;;
        *)
            echo "Invalid choice. Aborted."
            exit 1
            ;;
    esac
elif [ "$1" = "patch" ]; then
    NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
elif [ "$1" = "minor" ]; then
    NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
elif [ "$1" = "major" ]; then
    NEW_VERSION="$((MAJOR + 1)).0.0"
else
    # Assume it's a specific version number
    NEW_VERSION="$1"
fi

echo ""
echo "New version: $NEW_VERSION"
echo ""

# Confirm
read -p "Proceed with release v$NEW_VERSION? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 1: Updating version in pyproject.toml"
echo "=========================================="
sed -i "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
echo "Updated pyproject.toml to version $NEW_VERSION"

echo ""
echo "=========================================="
echo "Step 2: Building Debian package"
echo "=========================================="
./build-deb.sh

echo ""
echo "=========================================="
echo "Step 3: Installing package locally"
echo "=========================================="
PKG_FILE="dist/ai-repo-manager_${NEW_VERSION}_all.deb"
if [ ! -f "$PKG_FILE" ]; then
    echo "Error: Package file not found: $PKG_FILE"
    exit 1
fi
sudo dpkg -i "$PKG_FILE"

echo ""
echo "=========================================="
echo "Step 4: Committing changes"
echo "=========================================="
git add -A
git commit -m "v$NEW_VERSION: Release version $NEW_VERSION"

echo ""
echo "=========================================="
echo "Step 5: Creating git tag"
echo "=========================================="
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo ""
echo "=========================================="
echo "Step 6: Pushing to GitHub"
echo "=========================================="
git push origin main
git push origin "v$NEW_VERSION"

echo ""
echo "=========================================="
echo "Release complete!"
echo "=========================================="
echo "Version: v$NEW_VERSION"
echo "Package: $PKG_FILE"
echo ""
echo "GitHub release page:"
echo "  https://github.com/danielrosehill/AI-Repo-Manager/releases/tag/v$NEW_VERSION"
