#!/bin/bash
set -e

# Project root
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ROOT="$HOME/apimops_build"
VENV_DIR="$BUILD_ROOT/.venv"
BUILD_DIR="$BUILD_ROOT/build"
DIST_DIR="$BUILD_ROOT/dist"

# Deactivate any active venv
if [[ -n "$VIRTUAL_ENV" ]]; then
  deactivate || true
fi

# Create build dirs
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Create a fresh build venv if not present
if [ ! -d "$VENV_DIR" ]; then
  python3.12 -m venv "$VENV_DIR"
fi

# Activate the build venv
source "$VENV_DIR/bin/activate"

# Upgrade pip and install build dependencies
pip install --upgrade pip -q
pip install -r "$PROJECT_ROOT/build/requirements.txt" -q
pip install -r "$PROJECT_ROOT/scripts/setup/requirements.txt" -q
pip install -r "$PROJECT_ROOT/scripts/transfer/requirements.txt" -q

# Build executables for macOS (native)
echo "Building setup-macos..."
cd "$PROJECT_ROOT"
pyinstaller --clean --distpath "$DIST_DIR" --workpath "$BUILD_DIR" setup.spec

echo "Building transfer-macos..."
pyinstaller --clean --distpath "$DIST_DIR" --workpath "$BUILD_DIR" transfer.spec

echo "macOS executables created in $DIST_DIR:"
ls -lh "$DIST_DIR/"

# Copy config.yaml for testing
cp "$PROJECT_ROOT/config.yaml" "$DIST_DIR/config.yaml" 2>/dev/null || true

# Deactivate the build venv
deactivate

echo "Done."
