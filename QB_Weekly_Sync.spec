# QB_Weekly_Sync.spec — PyInstaller build spec
#
# Build with:
#   pyinstaller QB_Weekly_Sync.spec --clean
#
# Requires 32-bit Python 3.11 with all dependencies installed.

import glob
import os
import sys
from pathlib import Path

# Collect pywin32 system DLLs (pywintypes311.dll, pythoncom311.dll, etc.)
_site_packages = Path(sys.exec_prefix) / "Lib" / "site-packages"
_pywin32_dlls = glob.glob(str(_site_packages / "pywin32_system32" / "*.dll"))
_pywin32_binaries = [(dll, ".") for dll in _pywin32_dlls]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=_pywin32_binaries,
    datas=[],
    hiddenimports=[
        # pywin32
        "win32com",
        "win32com.client",
        "win32com.client.dynamic",
        "win32com.client.gencache",
        "win32com.server.util",
        "pywintypes",
        "win32timezone",
        "win32api",
        "win32con",
        # lxml
        "lxml._elementpath",
        "lxml.etree",
        # supabase / httpx stack
        "httpx",
        "httpcore",
        "httpcore._async",
        "httpcore._sync",
        "postgrest",
        "gotrue",
        "storage3",
        # standard-lib modules sometimes missed
        "email.mime.text",
        "email.mime.multipart",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="QB_Weekly_Sync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # keep console visible so log output is readable
    onefile=True,
)
