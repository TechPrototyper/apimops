# apimops Build Instructions

This directory contains scripts and configuration to build standalone executables for apimops for macOS, Linux, and Windows.

## Focus of Packaging

**Only the following tools are intended for end-user packaging and use:**
- `setup` (scripts/setup/setup.py): For environment and configuration setup.
- `transfer` (scripts/transfer/transfer.py): For API migration and transfer operations.

**Not included in the end-user CLI:**
- `asst` (scripts/asst/asst.py): Used for automation/CI (e.g., commit message generation), not for end-user CLI.
- `altersource/modify_code.sh`: For development/build customization only.

## Prerequisites

- Python 3.12 installed
- For building: PyInstaller (see `requirements.txt` in this folder)

## Usage

- On macOS:   ./build_mac.sh
- On Linux:   ./build_linux.sh
- On Windows: build_win.bat

The resulting executables will be in the `dist/` folder, named `setup` and `transfer` for each platform.
prlctl stop <vm-name> --kill
## Configuration

The executables expect a `config.yaml` file in the user's home directory:
- macOS/Linux: `~/.apimops/config.yaml`
- Windows: `%APPDATA%\apimops\config.yaml`
