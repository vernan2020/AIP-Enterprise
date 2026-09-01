from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY = "vernan2020/AIP-Enterprise"
BRANCH = "recovery/full-runtime-rc1-20260829"
CONTRACT_VERSION = "aip-runtime-checkpoint-v1"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_PATH = CHECKPOINT_DIR / "MANIFEST.json"
SUPPORT_FILES = (
    Path("scripts/recovery/checkpoint_contract.py"),
    Path("scripts/recovery/restore_runtime_checkpoint.py"),
    Path("scripts/recovery/runtime_checkpoint_status.py"),
    Path("scripts/recovery/verify_runtime_checkpoint.py"),
    Path("scripts/recovery/certify_installed_runtime.py"),
    Path("run_aip_configured.cmd"),
)
USER_AGENT = "AIP-Enterprise-RC1-Recovery/1.1"
_PART_NAME_RE = re.compile(r"^runtime_final\.part[0-9A-Za-z-]+\.b64$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _raw_url(path: Path) -> str:
    remote_path = urllib.parse.quote(path.as_posix(), safe="/")
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}/{remote_path}"


def _remote_file_bytes(remote_path: Path) -> bytes:
    request = urllib.request.Request(
        _raw_url(remote_path),
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if not data:
                raise RuntimeError(f"GitHub RAW returned empty content for {remote_path}")
            return data
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"GitHub RAW HTTP {exc.code} while reading {remote_path}"
                ) from exc
        except urllib.error.URLError as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(float(attempt))

    if isinstance(last_error, urllib.error.URLError):
        raise RuntimeError(
            f"Cannot reach GitHub RAW while reading {remote_path}: {last_error.reason}"
        ) from last_error
    raise RuntimeError(f"Unable to read GitHub RAW content for {remote_path}") from last_error


def _download_file(remote_path: Path, local_path: Path) -> None:
    data = _remote_file_bytes(remote_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = local_path.with_name(local_path.name + ".download")
    temporary.write_bytes(data)
    os.replace(temporary, local_path)


def _read_remote_manifest() -> dict[str, Any]:
    try:
        manifest = json.loads(_remote_file_bytes(MANIFEST_PATH).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Remote checkpoint manifest is invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("Remote checkpoint manifest is invalid")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise RuntimeError(
            "Remote checkpoint contract mismatch: "
            f"expected {CONTRACT_VERSION}, got {manifest.get('contract_version')!r}"
        )
    if manifest.get("checkpoint_directory") != CHECKPOINT_DIR.as_posix():
        raise RuntimeError("Remote checkpoint directory is inconsistent")
    if manifest.get("encoding") != "base64":
        raise RuntimeError("Remote checkpoint encoding is not base64")
    if manifest.get("archive_detection") != "tarfile r:*":
        raise RuntimeError("Remote checkpoint archive contract is inconsistent")

    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Remote checkpoint manifest has no parts")
    names: list[str] = []
    for item in parts:
        if not isinstance(item, str) or not _PART_NAME_RE.fullmatch(item):
            raise RuntimeError(f"Remote checkpoint has an invalid part name: {item!r}")
        names.append(item)
    if len(names) != len(set(names)):
        raise RuntimeError("Remote checkpoint manifest contains duplicate parts")
    if manifest.get("part_count") != len(names):
        raise RuntimeError("Remote checkpoint manifest part count is inconsistent")

    digest = manifest.get("payload_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise RuntimeError("Remote checkpoint manifest SHA-256 is invalid")

    critical = manifest.get("critical_members")
    if not isinstance(critical, list) or not critical:
        raise RuntimeError("Remote checkpoint manifest has no critical members")
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
    print("Transport: GitHub RAW")

    manifest = _read_remote_manifest()
    print(f"Checkpoint contract: {manifest['contract_version']}")
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
    else:
        print("Creating source rollback backup... skipped by caller")

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

    print("Restoring certified runtime transactionally...")
    restore_args = [sys.executable, "scripts/recovery/restore_runtime_checkpoint.py"]
    if skip_backup or backup is not None:
        restore_args.append("--skip-backup")
    _run(root, restore_args)

    print("Checking installed checkpoint marker and critical runtime...")
    _run(root, [sys.executable, "scripts/recovery/runtime_checkpoint_status.py"])

    runtime_env = _runtime_env(root)

    print("Compiling restored source tree...")
    _run(
        root,
        [sys.executable, "-m", "compileall", "-q", "src"],
        env=runtime_env,
    )

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
