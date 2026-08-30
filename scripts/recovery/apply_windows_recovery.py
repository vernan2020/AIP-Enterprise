from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from hashlib import sha256
from pathlib import Path

PACKAGE_DIR_NAME = "AIP_RC1_CERTIFIED"
PAYLOAD_DIR_NAME = "payload"
MANIFEST_NAME = "manifest.json"


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(package_root: Path) -> dict:
    manifest_path = package_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(f"Recovery manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Recovery manifest must be a JSON object")
    return payload


def _verify_payload(package_root: Path, manifest: dict) -> None:
    payload_root = package_root / PAYLOAD_DIR_NAME
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError("Recovery manifest does not declare payload files")

    expected_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise RuntimeError("Invalid recovery manifest entry")
        relative = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(relative, str) or not relative:
            raise RuntimeError("Recovery manifest contains an invalid path")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise RuntimeError(f"Unsafe recovery path: {relative}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise RuntimeError(f"Invalid recovery hash for {relative}")
        target = payload_root / candidate
        if not target.is_file():
            raise RuntimeError(f"Recovery payload file is missing: {relative}")
        actual_hash = _hash_file(target)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Recovery payload checksum mismatch for {relative}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        expected_paths.add(candidate.as_posix())

    actual_paths = {
        path.relative_to(payload_root).as_posix()
        for path in payload_root.rglob("*")
        if path.is_file()
    }
    extra = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    if extra or missing:
        raise RuntimeError(
            "Recovery payload file set mismatch: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )


def _resolve_project_root(package_root: Path, explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
    else:
        candidate = package_root.parent.resolve()

    if not (candidate / "src" / "aip").is_dir():
        raise RuntimeError(
            "Project root not detected. Extract AIP_RC1_CERTIFIED inside the "
            "AIP Enterprise project folder, or pass --project-root."
        )
    if not (candidate / "pyproject.toml").is_file():
        raise RuntimeError(f"pyproject.toml not found in project root: {candidate}")
    return candidate


def _backup_project(project_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = project_root / f"AIP_BEFORE_CERTIFIED_RECOVERY_{stamp}.zip"
    include_roots = [
        project_root / "src",
        project_root / "run_aip_configured.cmd",
        project_root / "scripts" / "recovery",
    ]
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in include_roots:
            if source.is_file():
                archive.write(source, source.relative_to(project_root).as_posix())
            elif source.is_dir():
                for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
                    archive.write(
                        file_path,
                        file_path.relative_to(project_root).as_posix(),
                    )
    return backup_path


def _copy_non_src_payload(payload_root: Path, project_root: Path) -> None:
    for source in sorted(path for path in payload_root.rglob("*") if path.is_file()):
        relative = source.relative_to(payload_root)
        if relative.parts and relative.parts[0] == "src":
            continue
        if relative.as_posix() == "config/runtime.local.cmd":
            continue
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _replace_src_transactionally(payload_root: Path, project_root: Path) -> None:
    incoming_src = payload_root / "src"
    if not incoming_src.is_dir():
        raise RuntimeError("Certified payload does not contain src")

    existing_src = project_root / "src"
    staging = project_root / ".aip_src_certified_staging"
    previous = project_root / ".aip_src_before_certified"

    for scratch in (staging, previous):
        if scratch.exists():
            shutil.rmtree(scratch)

    shutil.copytree(incoming_src, staging)
    if existing_src.exists():
        existing_src.rename(previous)
    try:
        staging.rename(existing_src)
    except Exception:
        if existing_src.exists():
            shutil.rmtree(existing_src)
        if previous.exists():
            previous.rename(existing_src)
        raise
    else:
        if previous.exists():
            shutil.rmtree(previous)


def _run_validation(project_root: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env.setdefault("AIP_EXECUTION_MODE", "CONFIGURED")
    env.setdefault("AIP_DEMO_MODE_ENABLED", "false")

    commands = [
        [sys.executable, "-m", "compileall", "-q", "src"],
        [sys.executable, "-m", "aip.tools.preflight_runtime"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=project_root, env=env, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                "Post-install validation failed: " + " ".join(command)
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply certified AIP RC1 runtime recovery")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args(argv)

    package_root = Path(__file__).resolve().parent
    manifest = _load_manifest(package_root)
    _verify_payload(package_root, manifest)
    project_root = _resolve_project_root(package_root, args.project_root)

    print(f"Certified recovery package: {manifest.get('package_version', 'unknown')}")
    print(f"Target project: {project_root}")
    print("Payload integrity: PASS")

    backup_path = _backup_project(project_root)
    print(f"Rollback backup: {backup_path.name}")

    try:
        _replace_src_transactionally(package_root / PAYLOAD_DIR_NAME, project_root)
        _copy_non_src_payload(package_root / PAYLOAD_DIR_NAME, project_root)
        marker = project_root / ".aip_certified_runtime.json"
        marker.write_text(
            json.dumps(
                {
                    "package_version": manifest.get("package_version"),
                    "source_commit": manifest.get("source_commit"),
                    "installed_at": datetime.now().isoformat(timespec="seconds"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _run_validation(project_root)
    except Exception as exc:
        print(f"RECOVERY FAILED: {exc}", file=sys.stderr)
        print(f"Rollback backup preserved at: {backup_path}", file=sys.stderr)
        return 1

    print("AIP certified runtime installed successfully.")
    print("Next step: run run_aip_configured.cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
