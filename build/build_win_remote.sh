#!/bin/bash
# build/build_win_remote.sh - Build Windows executables via Parallels VM
set -e

VM_NAME="${1:-Win11Automate}"
SHARE_NAME="apimops_build"

# Project root is where this script's parent directory is
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ROOT="$HOME/apimops_build"

# 1. Prepare build directory - copy project files
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"
cp -R "$PROJECT_ROOT"/* "$BUILD_ROOT"/
cp "$PROJECT_ROOT"/.gitignore "$BUILD_ROOT/" 2>/dev/null || true
cp "$PROJECT_ROOT"/.git "$BUILD_ROOT/"/.git -R 2>/dev/null || true

# 2. Remove the share if it exists (ignore errors)
prlctl set "$VM_NAME" --shf-host-del "$SHARE_NAME" 2>/dev/null || true

# Add the share
prlctl set "$VM_NAME" --shf-host-add "$SHARE_NAME" --path "$BUILD_ROOT" --mode rw

# 3. Start the VM if not running
if ! prlctl status "$VM_NAME" 2>/dev/null | grep -q "running"; then
  echo "Starting VM $VM_NAME..."
  prlctl start "$VM_NAME"
fi

# 4. Wait for SSH to be available
WIN_HOST="${WIN_HOST:-win11automate.local}"
WIN_USER="${WIN_USER:-admin}"
SSH_PORT=22

echo "Waiting for SSH on $WIN_HOST..."
until nc -z "$WIN_HOST" $SSH_PORT 2>/dev/null; do
  sleep 2
done
echo "SSH is up."

# 5. Remotely run the build script
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$WIN_USER@$WIN_HOST" \
  "cmd.exe /c \\\\mac\\apimops_build\\build\\build_win.bat"

# 6. Copy config.yaml to the dist directory
cp "$PROJECT_ROOT/config.yaml" "$BUILD_ROOT/build/dist/config.yaml" 2>/dev/null || true

# 7. Check build output
if [ -f "$BUILD_ROOT/build/dist/transfer.exe" ] && [ -f "$BUILD_ROOT/build/dist/setup.exe" ]; then
  echo "Windows executables built successfully."
  echo "Contents of dist directory:"
  ls -lh "$BUILD_ROOT/build/dist/"
  
  # Copy back to project binaries
  mkdir -p "$PROJECT_ROOT/binaries/v6.0.2/win-x64/publisher"
  mkdir -p "$PROJECT_ROOT/binaries/v6.0.2/win-x64/extractor"
else
  echo "Build may have failed or output not found."
  ls -la "$BUILD_ROOT/build/dist/" 2>/dev/null || true
  exit 1
fi

# 8. Cleanup share
prlctl set "$VM_NAME" --shf-host-del "$SHARE_NAME" 2>/dev/null || true

echo "Done."
