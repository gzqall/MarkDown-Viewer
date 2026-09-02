# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\Study\\Python\\markdown-viewer\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('renderer', 'renderer')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'numpy', 'scipy', 'pandas', 'PyQt6.QtBluetooth', 'PyQt6.QtNfc', 'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtTest', 'PyQt6.QtXml', 'PyQt6.QtSvg'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MarkdownViewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:\\Study\\Python\\markdown-viewer\\build_assets\\app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MarkdownViewer',
)
