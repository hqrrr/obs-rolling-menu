import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

from version import APP_NAME

# Config
ENTRY_FILE = "main.py"

DATA_DIRS = [
    ("ui", "ui"),
    ("fonts", "fonts"),
]


def clean_build_folders():
    """Remove PyInstaller build directories."""
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"Removed folder: {folder}")


def build():
    """Build the application using PyInstaller."""
    print("============================================")
    print(" Building OBS Rolling Menu")
    print("============================================")

    clean_build_folders()

    # Build PyInstaller command
    cmd = [
        "--name", APP_NAME,
        "--onefile",
        "--console",  # If no console wanted: replace with "--noconsole"
        ENTRY_FILE,
    ]

    # Add data folders
    for src, target in DATA_DIRS:
        cmd.append("--add-data")
        # Format: source_path:target_path (mac/linux)
        #         source_path;target_path (windows)
        sep = ";" if os.name == "nt" else ":"
        cmd.append(f"{src}{sep}{target}")

    print("\nRunning PyInstaller with arguments:")
    for c in cmd:
        print(" ", c)

    # Execute PyInstaller
    PyInstaller.__main__.run(cmd)

    print("============================================")
    print(" Build complete! Output in dist/")
    print("============================================")


def post_copy_external_assets(app_name: str):
    """
    After PyInstaller build, copy external runtime assets
    (excel, pics/, presets/) next to the built exe.
    """
    root = Path(__file__).resolve().parent
    dist_dir = root / "dist"

    if not dist_dir.exists():
        print("[PostBuild] dist directory not found, skip copying assets")
        return

    # if onefile: dist/app.exe
    exe_path = dist_dir / f"{app_name}.exe"

    # if onedir: dist/app/app.exe
    if not exe_path.exists():
        exe_path = dist_dir / app_name / f"{app_name}.exe"

    if not exe_path.exists():
        print("[PostBuild] exe not found, skip copying assets")
        return

    target_dir = exe_path.parent
    print(f"[PostBuild] Copy assets to: {target_dir}")

    # Excel
    excel_src = root / "data" / "data.xlsx"
    if excel_src.exists():
        shutil.copy2(excel_src, target_dir / excel_src.name)
        print(f"[PostBuild] Copied {excel_src.name}")

    # Directories
    for folder in ("pics", "presets"):
        src = root / folder
        dst = target_dir / folder

        if not src.exists():
            continue

        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        print(f"[PostBuild] Copied folder: {folder}")


if __name__ == "__main__":
    build()
    post_copy_external_assets(APP_NAME)
