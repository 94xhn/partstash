# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PartStash. Run from the repo root:

    pyinstaller packaging/ComponentsInventoryApp.spec
"""
import os

from PyInstaller.utils.hooks import collect_all

# ``SPECPATH`` is injected by PyInstaller and points at this file's directory
# (``packaging/``); the repo root is its parent.
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = [(os.path.join(REPO_ROOT, "app.py"), ".")]
binaries = []
hiddenimports = []
for pkg in ("streamlit", "plotly", "pandas"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[REPO_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="ComponentsInventoryApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
