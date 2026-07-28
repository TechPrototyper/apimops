# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for setup executable (build/ directory)
# When run from build/, SPECPATH points to build/; project_dir is parent

spec_dir = SPECPATH  # build/
project_dir = os.path.dirname(spec_dir)  # parent of build/
scripts_dir = os.path.join(project_dir, "scripts")

a = Analysis(
    [os.path.join(scripts_dir, "setup", "setup.py")],
    pathex=[os.path.join(scripts_dir, "common")],
    binaries=[],
    datas=[
        # Bundle apimops_utils.py at root level and scripts/common
        (os.path.join(scripts_dir, "common", "apimops_utils.py"), "."),
        (os.path.join(scripts_dir, "common", "apimops_utils.py"), "scripts/common"),
    ],
    hiddenimports=["apimops_utils"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
