from __future__ import annotations

import json
import os
import shutil
import zipfile
from hashlib import sha256
from pathlib import Path

PACKAGE_NAME = "AIP-Enterprise-RC1-Certified-Windows.zip"
PACKAGE_ROOT_NAME = "AIP_RC1_CERTIFIED"
INCLUDED_FILES = [
    Path("run_aip_configured.cmd"),
    Path("config/runtime.local.cmd.example"),
    Path("scripts/recovery/apply_windows_recovery.py"),
]
INCLUDED_DIRS = [
    Path("src"),
]
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _should_include(path: Path) -> bool:
    if any(part in EXCLUDED_NAMES for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith("~") or ".bak" in path.name.lower() or ".before_" in path.name.lower():
        return False
    return True


def _collect_files(root: Path) -> list[Path]:
    selected: set[Path] = set()
    for relative in INCLUDED_FILES:
        candidate = root / relative
        if not candidate.is_file():
            raise RuntimeError(f"Required package file is missing: {relative}")
        selected.add(relative)

    for relative_dir in INCLUDED_DIRS:
        directory = root / relative_dir
        if not directory.is_dir():
            raise RuntimeError(f"Required package directory is missing: {relative_dir}")
        for path in directory.rglob("*"):
            if path.is_file() and _should_include(path.relative_to(root)):
                selected.add(path.relative_to(root))

    return sorted(selected, key=lambda item: item.as_posix().lower())


def _write_apply_cmd(package_dir: Path) -> None:
    content = (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "python apply_windows_recovery.py\r\n"
        "if errorlevel 1 (\r\n"
        "  echo.\r\n"
        "  echo Recovery failed. The installer attempted automatic rollback.\r\n"
        "  echo Review the diagnostics above before retrying.\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        "echo.\r\n"
        "echo Recovery completed successfully.\r\n"
        "endlocal\r\n"
    )
    (package_dir / "APPLY_TO_PROJECT.cmd").write_text(content, encoding="utf-8", newline="")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    output = dist / PACKAGE_NAME

    with __import__("tempfile").TemporaryDirectory(prefix="aip-recovery-") as temp_name:
        temp_root = Path(temp_name)
        package_dir = temp_root / PACKAGE_ROOT_NAME
        payload_dir = package_dir / "payload"
        payload_dir.mkdir(parents=True, exist_ok=True)

        files = _collect_files(root)
        manifest_entries: list[dict[str, object]] = []
        for relative in files:
            source = root / relative
            destination = payload_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            manifest_entries.append(
                {
                    "path": relative.as_posix(),
                    "size": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            )

        installer_source = root / "scripts" / "recovery" / "apply_windows_recovery.py"
        shutil.copy2(installer_source, package_dir / "apply_windows_recovery.py")
        _write_apply_cmd(package_dir)

        source_commit = os.getenv("GITHUB_SHA", "local-build")
        manifest = {
            "package_name": PACKAGE_NAME,
            "package_version": "RC1-CERTIFIED-20260829",
            "source_branch": "recovery/full-runtime-rc1-20260829",
            "source_commit": source_commit,
            "file_count": len(manifest_entries),
            "files": manifest_entries,
            "preserved_local_assets": [
                ".venv",
                "database",
                "cache/runtime caches",
                "config/runtime.local.cmd",
            ],
            "installation_guarantees": [
                "payload SHA-256 is validated before installation",
                "existing recovery-owned runtime files are backed up before replacement",
                "src replacement is transactional",
                "local credentials are not packaged or overwritten",
                "compileall and configured preflight run before the certified marker is written",
                "failed post-install validation triggers automatic rollback to the pre-install runtime",
                "rollback backup is preserved after both successful and failed installation",
            ],
        }
        (package_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        if output.exists():
            output.unlink()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(package_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_root).as_posix())

    print(f"Certified package: {output}")
    print(f"SHA256: {_sha256(output)}")
    print(f"Files: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
