from __future__ import annotations

import compileall
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

REPOSITORY = "vernan2020/AIP-Enterprise"
BRANCH = "recovery/full-runtime-rc1-20260829"
ARCHIVE_URL = (
    "https://codeload.github.com/vernan2020/AIP-Enterprise/zip/refs/heads/"
    "recovery/full-runtime-rc1-20260829"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _backup_runtime(root: Path) -> Path:
    backup_dir = root / "recovery" / "local_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"AIP_PRE_QUICK_SYNC_{stamp}.zip"

    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        source_root = root / "src" / "aip"
        if source_root.exists():
            for path in source_root.rglob("*"):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                archive.write(path, path.relative_to(root))

        launcher = root / "run_aip_configured.cmd"
        if launcher.exists():
            archive.write(launcher, launcher.relative_to(root))

    return backup_path


def _download_archive(destination: Path) -> None:
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": "AIP-Enterprise-Recovery/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def _locate_prefix(archive: zipfile.ZipFile) -> str:
    names = archive.namelist()
    for name in names:
        if name.endswith("/src/aip/__init__.py"):
            return name[: -len("src/aip/__init__.py")]
    raise RuntimeError("Unable to locate src/aip in downloaded GitHub archive")


def _overlay_runtime(root: Path, archive_path: Path) -> int:
    copied = 0
    with zipfile.ZipFile(archive_path, "r") as archive:
        prefix = _locate_prefix(archive)
        source_prefix = prefix + "src/aip/"

        for info in archive.infolist():
            name = info.filename
            if info.is_dir() or not name.startswith(source_prefix):
                continue
            relative = Path(name[len(prefix):])
            if "__pycache__" in relative.parts or relative.suffix in {".pyc", ".pyo"}:
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            copied += 1

        launcher_name = prefix + "run_aip_configured.cmd"
        if launcher_name in archive.namelist():
            target = root / "run_aip_configured.cmd"
            with archive.open(launcher_name, "r") as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    return copied


def _runtime_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["AIP_EXECUTION_MODE"] = "CONFIGURED"
    env["AIP_DEMO_MODE_ENABLED"] = "false"
    env["PYTHONPATH"] = str(root / "src")
    env.setdefault("AIP_FOLDERWATCH_ENABLED", "true")
    env.setdefault("AIP_VECTOR_ENABLED", "true")
    env.setdefault("AIP_BCCR_ENABLED", "true")
    env.setdefault("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr")
    env.setdefault("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")
    return env


def _run_preflight(root: Path, env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "aip.tools.preflight_runtime"],
        cwd=root,
        env=env,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AIP preflight failed with exit code {result.returncode}")


def _run_smoke(root: Path, env: dict[str, str]) -> None:
    smoke_code = r'''
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap
from aip.product.configured.protocols import PortfolioDataProvider, LiquidityDataProvider, EconomicIndicatorsProvider
from aip.product.configured.services.configured_macro_intelligence_service import ConfiguredMacroIntelligenceService

loader = EnvironmentLoader()
config = loader.load()
sources = loader.load_source_config()
factory, _ = DemoBootstrap(config, source_config=sources).bootstrap(correlation_id="quick-recovery-smoke")
container = factory.container

portfolio = container.resolve(PortfolioDataProvider).get_portfolio()
liquidity = container.resolve(LiquidityDataProvider).get_liquidity()
macro = container.resolve(EconomicIndicatorsProvider).get_indicators()
projection = container.resolve(ConfiguredMacroIntelligenceService).get_projection()

print("AIP QUICK RECOVERY SMOKE")
print("EXECUTION_MODE=", config.execution_mode)
print("CUTOFF=", config.data_cutoff_date)
print("POSITIONS=", len(portfolio.get("positions", [])))
print("MARKET_VALUE=", portfolio.get("market_value"))
print("ICL_TOTAL=", liquidity.get("icl_total"))
print("ICL_SOURCE_DATE=", liquidity.get("icl_source_date"))
print("HQLA=", liquidity.get("hqla_capacity"))
print("MIL=", liquidity.get("mil_eligible_capacity"))
print("MACRO_STATUS=", macro.get("status"))
print("MACRO_INDICATORS=", len(macro.get("indicators", [])))
print("MACRO_SOURCE=", macro.get("source"))
print("SCENARIO_STATUS=", projection.get("status"))
print("SCENARIO_VERSION=", projection.get("version"))
print("SCENARIO_ROWS=", len(projection.get("rows", [])))
'''
    result = subprocess.run(
        [sys.executable, "-c", smoke_code],
        cwd=root,
        env=env,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AIP smoke test failed with exit code {result.returncode}")


def main() -> int:
    root = _project_root()
    print(f"AIP project root: {root}")
    print(f"Recovery branch: {BRANCH}")

    backup = _backup_runtime(root)
    print(f"Rollback backup: {backup}")

    with tempfile.TemporaryDirectory(prefix="aip-quick-sync-") as temporary:
        archive_path = Path(temporary) / "runtime.zip"
        print("Downloading recovered runtime from GitHub...")
        _download_archive(archive_path)
        print("Overlaying src/aip...")
        copied = _overlay_runtime(root, archive_path)
        print(f"Runtime files synchronized: {copied}")

    print("Compiling recovered runtime...")
    if not compileall.compile_dir(str(root / "src" / "aip"), quiet=1, force=True):
        raise RuntimeError("Python compileall failed")

    env = _runtime_environment(root)
    print("Running AIP preflight...")
    _run_preflight(root, env)
    print("Running institutional smoke test...")
    _run_smoke(root, env)

    print("AIP QUICK RECOVERY: READY")
    print("Launch with: run_aip_configured.cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
