# -*- mode: python ; coding: utf-8 -*-
"""Đóng gói GitShot thành 1 file GitShot.exe (PyInstaller, Windows)."""
from PyInstaller.utils.hooks import collect_all

datas = [("assets/icon.png", "assets"), ("assets/icon.ico", "assets")]
binaries = []
hiddenimports = []
for pkg in ("imageio_ffmpeg",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GitShot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
