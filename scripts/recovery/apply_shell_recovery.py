from __future__ import annotations

import compileall
import shutil
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

BRANCH = "recovery/full-runtime-rc1-20260829"
RAW_BASE = f"https://raw.githubusercontent.com/vernan2020/AIP-Enterprise/{BRANCH}"
FILES = (
    "src/aip/ui/shell/main_window.py",
    "src/aip/ui/shell/sidebar.py",
    "src/aip/ui/shell/ribbon.py",
)


def _download(relative_path: str, destination: Path) -> None:
    url = f"{RAW_BASE}/{relative_path}"
    request = urllib.request.Request(url, headers={"User-Agent": "AIP-Recovery/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload or b"class MainWindow" not in payload and relative_path.endswith("main_window.py"):
        raise RuntimeError(f"Invalid recovery payload: {relative_path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def main() -> int:
    root = Path.cwd()
    if not (root / "src" / "aip").is_dir():
        raise RuntimeError("Run this recovery from the AIP project root")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / "recovery" / "local_backups" / f"shell-{stamp}"

    with tempfile.TemporaryDirectory(prefix="aip-shell-recovery-") as tmp_name:
        tmp = Path(tmp_name)
        staged: dict[str, Path] = {}
        for relative in FILES:
            staged_path = tmp / relative
            _download(relative, staged_path)
            staged[relative] = staged_path

        if not compileall.compile_dir(str(tmp / "src"), quiet=1, force=True):
            raise RuntimeError("Recovered shell does not compile; local files were not changed")

        written: list[str] = []
        try:
            for relative in FILES:
                target = root / relative
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.copy2(target, backup)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged[relative], target)
                written.append(relative)

            if not compileall.compile_dir(
                str(root / "src" / "aip" / "ui" / "shell"),
                quiet=1,
                force=True,
            ):
                raise RuntimeError("Installed shell failed compilation")

        except Exception:
            for relative in reversed(written):
                target = root / relative
                backup = backup_root / relative
                if backup.exists():
                    shutil.copy2(backup, target)
            raise

    print("AIP shell recovery applied successfully")
    print(f"Backup: {backup_root}")
    print(f"Branch: {BRANCH}")
    for relative in FILES:
        print(f"OK: {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
