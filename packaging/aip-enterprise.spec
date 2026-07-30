# -*- mode: python -*-

block_cipher = None

a = Analysis(
    ["src/aip/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("config", "config"),
        ("src/aip/ui", "aip/ui"),
        ("src/aip/product/demo", "aip/product/demo"),
    ],
    hiddenimports=[
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="aip-enterprise",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="aip-enterprise",
)
