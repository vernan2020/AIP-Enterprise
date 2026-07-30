from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "packaging" / "aip-enterprise.spec"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    if sys.platform != "win32":
        print("Windows packaging scaffold validated only; full build requires a Windows host.")
        return 0
    if sys.version_info[:2] != (3, 13):
        fail("Python 3.13 is required for packaging.")
    if shutil.which("pyinstaller") is None:
        fail("PyInstaller is not available in the current environment.")
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
    result = subprocess.run(["pyinstaller", str(SPEC_FILE)], cwd=str(ROOT), check=False)
    if result.returncode != 0:
        fail("PyInstaller packaging failed.")
    print(f"Packaging output generated under {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
