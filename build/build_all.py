#!/usr/bin/env python3
"""
Universal Build Script for apimops Python utilities.
Builds executables for the current platform using PyInstaller.

Usage:
    python build_all.py              # Build for current platform
    python build_all.py --clean      # Clean and rebuild
    python build_all.py --list       # List what would be built

For Corporate environments (Zero Trust):
- All dependencies are pinned in requirements.txt
- Executables are self-contained (no Python installation needed on target)
- Builds work offline once venv is created
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

# Configuration
SCRIPTS_TO_BUILD = [
    {
        "name": "transfer",
        "entry": "scripts/transfer/transfer.py",
        "requirements": "scripts/transfer/requirements.txt",
        "extra_data": [("scripts/common/apimops_utils.py", ".")],
    },
    {
        "name": "setup", 
        "entry": "scripts/setup/setup.py",
        "requirements": "scripts/setup/requirements.txt",
        "extra_data": [],
    },
    {
        "name": "asst",
        "entry": "scripts/asst/asst.py",
        "requirements": "scripts/asst/requirements.txt",
        "extra_data": [],
    },
    {
        "name": "discover",
        "entry": "scripts/discover/discover.py",
        "requirements": "scripts/setup/requirements.txt",
        "extra_data": [],
    },
]

def get_platform_id():
    """Get platform identifier for directory naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        return "win-x64" if machine in ("amd64", "x86_64") else f"win-{machine}"
    elif system == "linux":
        return "linux-x64" if machine in ("x86_64",) else f"linux-{machine}"
    elif system == "darwin":
        return "osx-arm64" if machine == "arm64" else "osx-x64"
    return f"{system}-{machine}"

def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.resolve()

def setup_venv(venv_path: Path, requirements_files: list):
    """Create and setup virtual environment."""
    print(f"Setting up venv at {venv_path}...")
    
    if not venv_path.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    
    # Get pip path
    if platform.system() == "Windows":
        pip = venv_path / "Scripts" / "pip.exe"
        python = venv_path / "Scripts" / "python.exe"
    else:
        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"
    
    # Upgrade pip
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    
    # Install requirements
    for req_file in requirements_files:
        if req_file.exists():
            print(f"  Installing {req_file.name}...")
            subprocess.run([str(pip), "install", "-r", str(req_file)], check=True)
    
    # Install pyinstaller
    subprocess.run([str(pip), "install", "pyinstaller>=6.5.0"], check=True)
    
    return python

def build_executable(python_path: Path, script_config: dict, project_root: Path, dist_dir: Path, build_dir: Path):
    """Build a single executable using PyInstaller."""
    name = script_config["name"]
    entry = project_root / script_config["entry"]
    
    print(f"\nBuilding {name}...")
    
    if not entry.exists():
        print(f"  ERROR: Entry point not found: {entry}")
        return False
    
    # Build pyinstaller command
    cmd = [
        str(python_path), "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
        "--name", name,
    ]
    
    # Add extra data files
    for src, dst in script_config.get("extra_data", []):
        src_path = project_root / src
        if src_path.exists():
            cmd.extend(["--add-data", f"{src_path}{os.pathsep}{dst}"])
    
    cmd.append(str(entry))
    
    result = subprocess.run(cmd, cwd=str(project_root))
    
    if result.returncode == 0:
        exe_name = name + (".exe" if platform.system() == "Windows" else "")
        print(f"  SUCCESS: {dist_dir / exe_name}")
        return True
    else:
        print(f"  FAILED: Exit code {result.returncode}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build apimops executables")
    parser.add_argument("--clean", action="store_true", help="Clean build directories first")
    parser.add_argument("--list", action="store_true", help="List what would be built")
    args = parser.parse_args()
    
    project_root = get_project_root()
    platform_id = get_platform_id()
    
    build_root = Path.home() / "apimops_build" / platform_id
    venv_dir = build_root / "venv"
    build_dir = build_root / "build"
    dist_dir = build_root / "dist"
    
    print(f"=" * 60)
    print(f"APIMOPS Build Script")
    print(f"=" * 60)
    print(f"Platform:     {platform_id}")
    print(f"Project root: {project_root}")
    print(f"Build root:   {build_root}")
    print(f"Output:       {dist_dir}")
    print()
    
    if args.list:
        print("Scripts to build:")
        for s in SCRIPTS_TO_BUILD:
            entry = project_root / s["entry"]
            status = "OK" if entry.exists() else "MISSING"
            print(f"  - {s['name']:12} [{status}] {s['entry']}")
        return 0
    
    if args.clean:
        print("Cleaning build directories...")
        if build_root.exists():
            shutil.rmtree(build_root)
    
    # Create directories
    build_root.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all requirements files
    req_files = set()
    for s in SCRIPTS_TO_BUILD:
        req = project_root / s["requirements"]
        if req.exists():
            req_files.add(req)
    
    # Setup venv
    python_path = setup_venv(venv_dir, list(req_files))
    
    # Build each script
    results = []
    for script_config in SCRIPTS_TO_BUILD:
        success = build_executable(python_path, script_config, project_root, dist_dir, build_dir)
        results.append((script_config["name"], success))
    
    # Create distribution ZIP bundle
    import zipfile
    bundle_name = f"apimops-release-{platform_id}.zip"
    bundle_path = dist_dir / bundle_name
    print(f"\nPackaging distribution bundle: {bundle_name}...")
    
    with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add executables
        for script_config in SCRIPTS_TO_BUILD:
            exe_name = f"{script_config['name']}.exe" if platform.system() == "Windows" else script_config["name"]
            exe_path = dist_dir / exe_name
            if exe_path.exists():
                zipf.write(exe_path, arcname=exe_name)
        
        # Add template config & documentation
        for doc_file in ["config.template.yaml", "README.md", "LICENSE"]:
            doc_path = project_root / doc_file
            if doc_path.exists():
                zipf.write(doc_path, arcname=doc_file)
        
        guide_path = project_root / "docs" / "CORPORATE_ADMIN_GUIDE.md"
        if guide_path.exists():
            zipf.write(guide_path, arcname="docs/CORPORATE_ADMIN_GUIDE.md")

    print(f"Bundle created at: {bundle_path}")

    # Summary
    print()
    print("=" * 60)
    print("BUILD SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "OK" if success else "FAILED"
        print(f"  {name:12} [{status}]")
    
    print(f"  {'bundle':12} [OK] ({bundle_name})")
    print()
    print(f"Executables in: {dist_dir}")
    
    return 0 if all(s for _, s in results) else 1

if __name__ == "__main__":
    sys.exit(main())
