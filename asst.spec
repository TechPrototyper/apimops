# -*- mode: python ; coding: utf-8 -*-


project_dir = SPECPATH
scripts_dir = os.path.join(project_dir, "scripts")

a = Analysis(
    [os.path.join(scripts_dir, "asst", "asst.py")],
    pathex=[os.path.join(scripts_dir, "common")],
    binaries=[],
    datas=[
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
    name='asst',
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
