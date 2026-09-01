from __future__ import annotations

import compileall
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

BRANCH = "recovery/full-runtime-rc1-20260829"
URL = f"https://codeload.github.com/vernan2020/AIP-Enterprise/zip/refs/heads/{BRANCH}"
CRITICAL = (
    "src/aip/tools/preflight_runtime.py",
    "src/aip/product/configured/services/configured_portfolio_var_service.py",
    "src/aip/product/economic/economic_snapshot_store.py",
    "src/aip/ui/modules/macro_intelligence/views/macro_intelligence_view.py",
)


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def tls() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return ctx


def backup(project: Path) -> Path:
    out = project / "recovery" / "local_backups"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"AIP_PRE_QUICK_SYNC_V2_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        src = project / "src" / "aip"
        if src.exists():
            for p in src.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}:
                    z.write(p, p.relative_to(project))
        for rel in (Path("run_aip_configured.cmd"), Path("scripts/recovery/enable_macro_projection.py")):
            p = project / rel
            if p.exists():
                z.write(p, rel)
    return path


def restore(project: Path, archive: Path) -> None:
    target = project / "src" / "aip"
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise RuntimeError(f"Unsafe rollback member: {name}")
            if name.startswith("src/aip/") or name in {"run_aip_configured.cmd", "scripts/recovery/enable_macro_projection.py"}:
                z.extract(name, project)


def download(path: Path) -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "AIP-Recovery-V2/1"})
    with urllib.request.urlopen(req, timeout=120, context=tls()) as r:
        path.write_bytes(r.read())


def canonical_prefix(z: zipfile.ZipFile) -> str:
    suffix = "src/aip/__init__.py"
    candidates = [n[:-len(suffix)] for n in z.namelist() if n.endswith(suffix)]
    if not candidates:
        raise RuntimeError("src/aip not found in GitHub archive")
    prefix = min(candidates, key=lambda x: (x.count("/"), len(x)))
    missing = [prefix + rel for rel in CRITICAL if prefix + rel not in z.namelist()]
    if missing:
        raise RuntimeError("Canonical runtime incomplete: " + ", ".join(missing))
    return prefix


def stage(archive: Path, stage_root: Path) -> int:
    count = 0
    with zipfile.ZipFile(archive) as z:
        prefix = canonical_prefix(z)
        source_prefix = prefix + "src/aip/"
        print("Canonical prefix:", prefix)
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(source_prefix):
                continue
            rel = Path(info.filename[len(prefix):])
            if "__pycache__" in rel.parts or rel.suffix in {".pyc", ".pyo"}:
                continue
            dest = stage_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
        for rel in ("run_aip_configured.cmd", "scripts/recovery/enable_macro_projection.py"):
            member = prefix + rel
            if member in z.namelist():
                dest = stage_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    return count


def overlay(source: Path, destination: Path) -> int:
    count = 0
    for p in source.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix in {".pyc", ".pyo"}:
            continue
        dest = destination / p.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        count += 1
    return count


def env(project: Path) -> dict[str, str]:
    e = os.environ.copy()
    e["PYTHONPATH"] = str(project / "src")
    e["AIP_EXECUTION_MODE"] = "CONFIGURED"
    e["AIP_DEMO_MODE_ENABLED"] = "false"
    e.setdefault("AIP_FOLDERWATCH_ENABLED", "true")
    e.setdefault("AIP_VECTOR_ENABLED", "true")
    e.setdefault("AIP_BCCR_ENABLED", "true")
    e.setdefault("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr")
    e.setdefault("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")
    return e


def checked(cmd: list[str], project: Path, environment: dict[str, str], label: str) -> None:
    result = subprocess.run(cmd, cwd=project, env=environment, check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def main() -> int:
    project = root()
    rollback = backup(project)
    print("AIP project root:", project)
    print("Recovery branch:", BRANCH)
    print("Rollback backup:", rollback)
    try:
        with tempfile.TemporaryDirectory(prefix="aip-sync-v2-") as td:
            temp = Path(td)
            archive = temp / "branch.zip"
            staged = temp / "stage"
            staged.mkdir()
            print("Downloading canonical runtime...")
            download(archive)
            count = stage(archive, staged)
            print("Staged runtime files:", count)
            if count < 100:
                raise RuntimeError(f"Refusing incomplete runtime with only {count} files")
            if not compileall.compile_dir(str(staged / "src" / "aip"), quiet=1, force=True):
                raise RuntimeError("Staged compileall failed")
            copied = overlay(staged / "src" / "aip", project / "src" / "aip")
            print("Runtime files synchronized:", copied)
            for rel in (Path("run_aip_configured.cmd"), Path("scripts/recovery/enable_macro_projection.py")):
                src = staged / rel
                if src.exists():
                    dst = project / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        environment = env(project)
        if not compileall.compile_dir(str(project / "src" / "aip"), quiet=1, force=True):
            raise RuntimeError("Local compileall failed")
        checked([sys.executable, "-m", "aip.tools.preflight_runtime"], project, environment, "AIP preflight")
        print("AIP QUICK SYNC V2: READY")
        print("Next: run_aip_configured.cmd")
        return 0
    except Exception:
        print("Sync failed; restoring rollback:", rollback)
        restore(project, rollback)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
