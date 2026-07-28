# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for discover executable (build/ directory)

spec_dir = SPECPATH  # build/
project_dir = os.path.dirname(spec_dir)  # parent of build/
scripts_dir = os.path.join(project_dir, "scripts")

a = Analysis(
    [os.path.join(scripts_dir, "discover", "discover.py")],
    pathex=[os.path.join(scripts_dir, "common")],
    binaries=[],
    datas=[
        (os.path.join(scripts_dir, "common", "apimops_utils.py"), "."),
        (os.path.join(scripts_dir, "common", "apimops_utils.py"), "scripts/common"),
    ],
    hiddenimports=["apimops_utils", "azure.identity", "azure.mgmt.resource", "azure.mgmt.apimanagement"],
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
    name='discover',
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
