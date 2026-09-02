"""
Markdown Viewer — Windows 安装包构建脚本
1. PyInstaller 打包 Python 应用
2. NSIS 制作安装程序
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
NSIS_EXE = r"C:\Program Files (x86)\NSIS\makensis.exe"


def clean():
    """清理之前的构建产物"""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    # 清理 PyInstaller 生成的 spec 文件
    for f in BASE_DIR.glob("*.spec"):
        f.unlink()
    print("[Clean] Done")


def build_app():
    """用 PyInstaller 打包应用"""
    print("\n=== Step 1: PyInstaller ===")

    # 构建 renderer 数据路径参数
    renderer_path = f"renderer{os.pathsep}renderer"

    # Icon path for the executable
    icon_path = BASE_DIR / "build_assets" / "app.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "MarkdownViewer",
        "--icon", str(icon_path),
        "--add-data", renderer_path,
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        # 优化: 排除不需要的模块
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PIL",
        "--exclude-module", "numpy",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "PyQt6.QtBluetooth",
        "--exclude-module", "PyQt6.QtNfc",
        "--exclude-module", "PyQt6.QtPositioning",
        "--exclude-module", "PyQt6.QtSensors",
        "--exclude-module", "PyQt6.QtTest",
        "--exclude-module", "PyQt6.QtXml",
        "--exclude-module", "PyQt6.QtSvg",
        str(BASE_DIR / "main.py"),
    ]

    print("Running PyInstaller...")
    subprocess.check_call(cmd, cwd=str(BASE_DIR))

    # 确保 vendor 目录被包含
    app_dir = DIST_DIR / "MarkdownViewer"
    target_vendor = app_dir / "renderer" / "vendor"
    source_vendor = BASE_DIR / "renderer" / "vendor"
    if source_vendor.exists() and not target_vendor.exists():
        print("Copying vendor files...")
        shutil.copytree(source_vendor, target_vendor)

    print(f"[PyInstaller] App built at: {app_dir}")


def create_installer():
    """用 NSIS 制作安装程序"""
    print("\n=== Step 2: NSIS Installer ===")

    if not os.path.exists(NSIS_EXE):
        print(f"[NSIS] Not found: {NSIS_EXE}")
        print("[NSIS] Skipping installer creation")
        return

    # 确保 NSIS 脚本中的版本号与 app 一致
    nsi_script = BASE_DIR / "installer.nsi"

    if not nsi_script.exists():
        print(f"[NSIS] Script not found: {nsi_script}")
        return

    print("Compiling NSIS installer...")
    subprocess.check_call([NSIS_EXE, str(nsi_script)], cwd=str(BASE_DIR))

    # 查找生成的安装包
    installer = DIST_DIR / "MarkdownViewer-Setup.exe"
    if installer.exists():
        size_mb = installer.stat().st_size / (1024 * 1024)
        print(f"[NSIS] Installer created: {installer} ({size_mb:.1f} MB)")
    else:
        print("[NSIS] Installer not found at expected location, checking dist/...")
        for f in DIST_DIR.glob("*.exe"):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  Found: {f} ({size_mb:.1f} MB)")


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  Markdown Viewer - Windows Build Script      ║")
    print("╚══════════════════════════════════════════════╝")

    clean()
    build_app()
    create_installer()

    print("\n=== Build Complete ===")
    installer = DIST_DIR / "MarkdownViewer-Setup.exe"
    if installer.exists():
        size_mb = installer.stat().st_size / (1024 * 1024)
        print(f"Installer: {installer} ({size_mb:.1f} MB)")
        print("Copy this file to any Windows machine and run it!")
    else:
        app_dir = DIST_DIR / "MarkdownViewer"
        if app_dir.exists():
            print(f"Portable app: {app_dir}")
            print("You can run MarkdownViewer.exe directly from this folder.")


if __name__ == "__main__":
    main()
