from __future__ import annotations

import runpy
import shutil
import ssl
import urllib.request
import zipfile
from pathlib import Path

BRANCH = "recovery/full-runtime-rc1-20260829"
V2_URL = (
    "https://raw.githubusercontent.com/vernan2020/AIP-Enterprise/"
    f"{BRANCH}/scripts/recovery/quick_sync_runtime_v2.py"
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def healthy_backup(root: Path) -> Path | None:
    folder = root / "recovery" / "local_backups"
    candidates = sorted(folder.glob("AIP_PRE_QUICK_SYNC_*.zip"), reverse=True) if folder.exists() else []
    for backup in candidates:
        try:
            with zipfile.ZipFile(backup) as archive:
                if "src/aip/tools/preflight_runtime.py" in archive.namelist():
                    return backup
        except (OSError, zipfile.BadZipFile):
            continue
    return None


def restore(root: Path, backup: Path) -> None:
    target = root / "src" / "aip"
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(backup) as archive:
        for name in archive.namelist():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"Unsafe backup member: {name}")
            if name.startswith("src/aip/") or name in {
                "run_aip_configured.cmd",
                "scripts/recovery/enable_macro_projection.py",
            }:
                archive.extract(name, root)


def tls() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return context


def main() -> int:
    root = project_root()
    preflight = root / "src" / "aip" / "tools" / "preflight_runtime.py"
    if not preflight.exists():
        backup = healthy_backup(root)
        if backup is None:
            print("No healthy local backup found; V2 canonical overlay will attempt repair directly.")
        else:
            print("Restoring healthy pre-sync backup:", backup)
            restore(root, backup)
            print("Healthy backup restored.")
    else:
        print("Base runtime is intact; no rollback restoration needed.")

    v2 = root / "scripts" / "recovery" / "quick_sync_runtime_v2.py"
    request = urllib.request.Request(V2_URL, headers={"User-Agent": "AIP-Recovery-Repair/1"})
    with urllib.request.urlopen(request, timeout=60, context=tls()) as response:
        v2.write_bytes(response.read())
    print("Executing canonical quick sync V2:", v2)
    runpy.run_path(str(v2), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
