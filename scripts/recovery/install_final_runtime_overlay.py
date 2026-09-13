from __future__ import annotations

import argparse
import base64
import compileall
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen


REPOSITORY = "vernan2020/AIP-Enterprise"
BASE_SHA = "06ef49734520487bfb715040e61d588bd35f3dec"
TARGET_SHA = "9d9d3f5be7eaa46381703035f6f017b1449dfbee"
USER_AGENT = "AIP-Enterprise-RC1-Final-Overlay/1.0"


def _request_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request, timeout=60) as response:
        return response.read()


def _git_blob_sha(data: bytes) -> str:
    prefix = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(prefix + data).hexdigest()


def _safe_source_path(filename: str) -> PurePosixPath:
    path = PurePosixPath(filename)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe repository path: {filename}")
    if not path.parts or path.parts[0] != "src":
        raise RuntimeError(f"Overlay attempted outside src: {filename}")
    return path


def _compare_files() -> list[dict[str, object]]:
    url = (
        f"https://api.github.com/repos/{REPOSITORY}/compare/"
        f"{BASE_SHA}...{TARGET_SHA}?per_page=250"
    )
    payload = json.loads(_request_bytes(url).decode("utf-8"))
    if payload.get("status") not in {"ahead", "identical"}:
        raise RuntimeError(
            "Final overlay target is not a forward descendant of the certified base."
        )
    files = payload.get("files")
    if not isinstance(files, list):
        raise RuntimeError("GitHub compare response does not contain a file list.")
    return [
        item
        for item in files
        if isinstance(item, dict)
        and str(item.get("filename") or "").startswith("src/")
    ]


def _download_source_file(filename: str, expected_sha: str | None) -> bytes:
    encoded_path = quote(filename, safe="/")
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/"
        f"{TARGET_SHA}/{encoded_path}"
    )
    data = _request_bytes(url)
    if expected_sha:
        actual = _git_blob_sha(data)
        if actual != expected_sha:
            raise RuntimeError(
                f"Integrity failure for {filename}: expected {expected_sha}, got {actual}"
            )
    if filename.endswith(".py") and b"\x00" in data:
        raise RuntimeError(f"Invalid NUL byte in Python source: {filename}")
    return data


def _backup_file(project_root: Path, backup_root: Path, relative: PurePosixPath) -> None:
    source = project_root.joinpath(*relative.parts)
    if not source.exists():
        return
    destination = backup_root.joinpath(*relative.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _apply_overlay(project_root: Path, files: list[dict[str, object]]) -> int:
    staging = Path(tempfile.mkdtemp(prefix=".aip-final-overlay-", dir=project_root))
    backup = staging / "backup"
    staged = staging / "staged"
    changed = 0
    try:
        prepared: list[tuple[PurePosixPath, str, bytes | None, PurePosixPath | None]] = []
        for item in files:
            filename = str(item.get("filename") or "")
            status = str(item.get("status") or "")
            relative = _safe_source_path(filename)
            previous: PurePosixPath | None = None
            previous_name = item.get("previous_filename")
            if previous_name:
                previous = _safe_source_path(str(previous_name))

            if status == "removed":
                prepared.append((relative, status, None, previous))
                continue

            expected_sha = str(item.get("sha") or "") or None
            data = _download_source_file(filename, expected_sha)
            staged_path = staged.joinpath(*relative.parts)
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_bytes(data)
            prepared.append((relative, status, data, previous))

        for relative, status, data, previous in prepared:
            if previous is not None and previous != relative:
                _backup_file(project_root, backup, previous)
                old_path = project_root.joinpath(*previous.parts)
                if old_path.exists():
                    old_path.unlink()

            _backup_file(project_root, backup, relative)
            destination = project_root.joinpath(*relative.parts)
            if status == "removed":
                if destination.exists():
                    destination.unlink()
                    changed += 1
                continue

            assert data is not None
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".aip-overlay.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, destination)
            changed += 1

        print(f"Overlay source files applied: {changed}")
        return changed
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _compile_source(project_root: Path) -> None:
    print("Compiling final source tree...")
    if not compileall.compile_dir(
        str(project_root / "src"),
        quiet=1,
        force=True,
    ):
        raise RuntimeError("Python source compilation failed.")
    print("Source compilation: PASS")


def _run_deep_certification(project_root: Path) -> None:
    certifier = project_root / "scripts" / "recovery" / "certify_installed_runtime.py"
    if not certifier.is_file():
        raise RuntimeError(f"Runtime certifier not found: {certifier}")
    print("Running deep configured-runtime certification...")
    subprocess.run(
        [sys.executable, str(certifier)],
        cwd=project_root,
        env=os.environ.copy(),
        check=True,
    )
    print("Deep configured-runtime certification: PASS")


def _run_final_market_ui_smoke(project_root: Path) -> None:
    code = r'''
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QSplitter, QTabWidget
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.environment_loader import EnvironmentLoader
from aip.ui.modules.market.presenters.market_presenter import MarketPresenter
from aip.ui.modules.market.views.market_view import MarketView

app = QApplication.instance() or QApplication([])
loader = EnvironmentLoader()
factory = DemoApplicationFactory(loader.load(), source_config=loader.load_source_config())
view = MarketView(presenter=MarketPresenter(factory))
assert view.view_model().status == "loaded"
assert view.findChild(QSplitter, "marketAnalyticalSplitter") is not None
tabs = view.findChild(QTabWidget, "marketRelativeValueTabs")
assert tabs is not None and tabs.count() == 3
assert tabs.tabText(0).startswith("RV Portafolio")
assert tabs.tabText(1).startswith("RV Mercado")
assert tabs.tabText(2).startswith("Rotación")
print("FINAL MARKET UI SMOKE: PASS")
view.close()
app.processEvents()
'''
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["PYTHONPATH"] = str(project_root / "src")
    print("Running final Market UI smoke against configured sources...")
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        env=env,
        check=True,
        timeout=300,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the immutable AIP RC1 final runtime/UI overlay."
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="AIP project root. Defaults to the current directory.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not (project_root / "src" / "aip").is_dir():
        raise SystemExit(f"AIP source tree not found under {project_root}")

    print("=== AIP ENTERPRISE RC1 - FINAL RUNTIME/UI OVERLAY ===")
    print(f"Certified base: {BASE_SHA}")
    print(f"Final source commit: {TARGET_SHA}")
    print(f"Project root: {project_root}")

    files = _compare_files()
    print(f"Source changes to reconcile: {len(files)}")
    if not files:
        raise RuntimeError("No source changes were returned for the final overlay.")

    _apply_overlay(project_root, files)
    _compile_source(project_root)
    _run_deep_certification(project_root)
    _run_final_market_ui_smoke(project_root)

    print("=== FINAL RUNTIME/UI CERTIFICATION: PASS ===")
    print("The application may now be launched with run_aip_configured.cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
