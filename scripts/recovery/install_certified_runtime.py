from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY = "vernan2020/AIP-Enterprise"
BRANCH = "recovery/full-runtime-rc1-20260829"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_PATH = CHECKPOINT_DIR / "MANIFEST.json"
SUPPORT_FILES = (
    Path("scripts/recovery/restore_runtime_checkpoint.py"),
    Path("scripts/recovery/runtime_checkpoint_status.py"),
    Path("scripts/recovery/verify_runtime_checkpoint.py"),
    Path("scripts/recovery/certify_installed_runtime.py"),
    Path("run_aip_configured.cmd"),
)
USER_AGENT = "AIP-Enterprise-RC1-Recovery/1.0"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _api_url(path: Path) -> str:
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.parts)
    query = urllib.parse.urlencode({"ref": BRANCH})
    return f"https://api.github.com/repos/{REPOSITORY}/contents/{encoded_path}?{query}"


def _fetch_json(path: Path) -> dict[str, Any]:
    request = urllib.request.Request(
        _api_url(path),
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub HTTP {exc.code} while reading {path}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach GitHub while reading {path}: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected GitHub response for {path}")
    return payload


def _download_file(remote_path: Path, local_path: Path) -> None:
    payload = _fetch_json(remote_path)
    if payload.get("type") != "file":
        raise RuntimeError(f"GitHub path is not a file: {remote_path}")
    encoded = payload.get("content")
    encoding = payload.get("encoding")
    if encoding != "base64" or not isinstance(encoded, str):
        raise RuntimeError(f"Unsupported GitHub content encoding for {remote_path}")
    try:
        data = base64.b64decode(encoded, validate=False)
    except Exception as exc:
        raise RuntimeError(f"Invalid GitHub base64 content for {remote_path}") from exc

    local_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = local_path.with_name(local_path.name + ".download")
    temporary.write_bytes(data)
    os.replace(temporary, local_path)


def _read_remote_manifest() -> dict[str, Any]:
    payload = _fetch_json(MANIFEST_PATH)
    encoded = payload.get("content")
    if payload.get("encoding") != "base64" or not isinstance(encoded, str):
        raise RuntimeError("Remote checkpoint manifest has unsupported encoding")
    manifest = json.loads(base64.b64decode(encoded).decode("utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("Remote checkpoint manifest is invalid")
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Remote checkpoint manifest has no parts")
    if manifest.get("part_count") != len(parts):
        raise RuntimeError("Remote checkpoint manifest part count is inconsistent")
    digest = manifest.get("payload_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError("Remote checkpoint manifest SHA-256 is invalid")
    return manifest


def _backup_src(root: Path) -> Path | None:
    source = root / "src"
    if not source.is_dir():
        return None
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = root / f"AIP_BEFORE_CERTIFIED_RUNTIME_{timestamp}.zip"
    excluded_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    excluded_suffixes = {".pyc", ".pyo"}
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in excluded_names for part in relative.parts):
                continue
            if path.suffix.lower() in excluded_suffixes:
                continue
            archive.write(path, relative.as_posix())
    return backup


def _run(root: Path, args: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(args, cwd=root, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {' '.join(args)}"
        )


def _runtime_env(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AIP_EXECUTION_MODE"] = "CONFIGURED"
    env["AIP_DEMO_MODE_ENABLED"] = "false"
    env["PYTHONPATH"] = str(root / "src")
    env.setdefault("AIP_FOLDERWATCH_ENABLED", "true")
    env.setdefault("AIP_VECTOR_ENABLED", "true")
    env.setdefault("AIP_BCCR_ENABLED", "true")
    env.setdefault("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr")
    env.setdefault("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")
    return env


def install(*, skip_backup: bool = False) -> int:
    root = _project_root()
    print("AIP ENTERPRISE - CERTIFIED RUNTIME INSTALLER")
    print(f"Project root: {root}")
    print(f"Source branch: {BRANCH}")

    manifest = _read_remote_manifest()
    print(f"Checkpoint SHA-256: {manifest['payload_sha256']}")
    print(f"Checkpoint parts: {manifest['part_count']}")

    backup: Path | None = None
    if not skip_backup:
        print("Creating source rollback backup...")
        backup = _backup_src(root)
        if backup is not None:
            print(f"Backup: {backup.name}")
        else:
            print("Backup: source tree not present; skipped")

    print("Downloading recovery support files...")
    for remote in SUPPORT_FILES:
        _download_file(remote, root / remote)

    print("Downloading certified checkpoint manifest...")
    _download_file(MANIFEST_PATH, root / MANIFEST_PATH)

    checkpoint_local = root / CHECKPOINT_DIR
    declared_names = {str(name) for name in manifest["parts"]}
    for existing in checkpoint_local.glob("runtime_final.part*.b64"):
        if existing.name not in declared_names:
            existing.unlink()

    for index, name in enumerate(manifest["parts"], start=1):
        remote = CHECKPOINT_DIR / str(name)
        print(f"Downloading checkpoint part {index}/{manifest['part_count']}: {name}")
        _download_file(remote, root / remote)

    print("Verifying checkpoint before extraction...")
    _run(root, [sys.executable, "scripts/recovery/verify_runtime_checkpoint.py"])

    print("Restoring certified runtime...")
    _run(root, [sys.executable, "scripts/recovery/restore_runtime_checkpoint.py"])

    runtime_env = _runtime_env(root)

    print("Running configured preflight...")
    _run(
        root,
        [sys.executable, "-m", "aip.tools.preflight_runtime"],
        env=runtime_env,
    )

    print("Running deep runtime certification...")
    _run(
        root,
        [sys.executable, "scripts/recovery/certify_installed_runtime.py"],
        env=runtime_env,
    )

    print()
    print("CERTIFIED RUNTIME INSTALLATION: PASS")
    if backup is not None:
        print(f"Rollback backup retained: {backup}")
    print("Start AIP with: run_aip_configured.cmd")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and certify the AIP Enterprise RC1 runtime from GitHub without Git."
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Do not create a ZIP backup of the existing src tree.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return install(skip_backup=args.skip_backup)
    except Exception as exc:
        print()
        print(f"CERTIFIED RUNTIME INSTALLATION: FAILED - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
