#!/bin/bash
set -e
cd "$(dirname "$0")"

BUILD_ROOT="$HOME/apimops_build"
VENV_DIR="$BUILD_ROOT/venv"
BUILD_DIR="$BUILD_ROOT/build"
DIST_DIR="$BUILD_ROOT/dist"

python3.12 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r ../scripts/setup/requirements.txt
pip install -r requirements.txt
pyinstaller --clean --onefile --distpath "$DIST_DIR" --workpath "$BUILD_DIR" --name setup ../scripts/setup/setup.py
pyinstaller --clean --onefile --distpath "$DIST_DIR" --workpath "$BUILD_DIR" --name transfer ../scripts/transfer/transfer.py
deactivate
echo "Executables created in $DIST_DIR: setup, transfer"
