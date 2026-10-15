"""Fail-closed AIP PREVIEW updater. Never writes to the certified release.

The ZIP was assembled at a GitHub-verified commit. Verify SHA-256 on every
source before any modification, back up originals, then atomically replace.
Does not touch environment files, DuckDB, credential files, fonts or .venv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

FORMAT = "aip-v451-preview-patch-v1"
PROTECTED = frozenset(
    {
        ".env",
        ".env.local",
        ".git",
        ".venv",
        "database",
        "__pycache__",
        "runtime.local.cmd",
        "runtime.local.env",
    }
)
NO_COPY_EXT = frozenset({".ttf", ".otf", ".woff", ".woff2", ".duckdb", ".db", ".wal", ".pyc"})


class UpdateRejected(Exception):
    """Unsafe or unverifiable update request."""


def validate_path(name: str) -> Path:
    candidate = PurePosixPath(name)
    parts = candidate.parts
    if (
        not parts
        or candidate.is_absolute()
        or "\\" in name
        or ".." in parts
        or any(part.lower() in PROTECTED for part in parts)
        or candidate.suffix.lower() in NO_COPY_EXT
        or not (
            (len(parts) > 1 and parts[0] in ("src", "scripts"))
            or name
            in {
                "main.py",
                "pyproject.toml",
                "run_aip_configured.cmd",
                "run_aip_ux_preview.cmd",
                "DIAGNOSTICAR_BCCR_SUGEF.cmd",
        "DIAGNOSTICAR_RTILB_XML.cmd",
                "AUDITAR_FUENTES_CONFIGURADAS.cmd",
                "INSPECCIONAR_HISTORICOS_PREVIEW.cmd",
            }
        )
    ):
        raise UpdateRejected("forbidden manifest path")
    return Path(*parts)


def verify_payload(package_root: Path) -> tuple[dict, list[tuple[Path, Path]]]:
    try:
        manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpdateRejected("manifest missing or invalid") from exc
    if (
        manifest.get("format") != FORMAT
        or manifest.get("repository") != "vernan2020/AIP-Enterprise"
        or manifest.get("target_name") != "AIP-V451-PREVIEW"
        or not isinstance(manifest.get("source_sha"), str)
        or len(manifest["source_sha"]) != 40
        or not isinstance(manifest.get("files"), list)
        or not manifest["files"]
    ):
        raise UpdateRejected("unsupported manifest")
    files: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not all(
            key in entry for key in ("path", "sha256", "size")
        ):
            raise UpdateRejected("invalid file entry")
        relative = validate_path(entry["path"])
        key = relative.as_posix().casefold()
        if key in seen:
            raise UpdateRejected("duplicate file entry")
        seen.add(key)
        source = package_root / "payload" / relative
        if not source.is_file() or source.is_symlink():
            raise UpdateRejected("missing or linked package member")
        payload = source.read_bytes()
        if len(payload) != entry["size"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise UpdateRejected("SHA256 mismatch in payload")
        files.append((relative, source))
    if not any(path.as_posix().startswith("src/aip/") for path, _ in files):
        raise UpdateRejected("AIP source missing")
    return manifest, files


def _validate_target(target: Path) -> Path:
    # PREVIEW path is the only valid destination, including test installations.
    if target.name.casefold() != "aip-v451-preview" or not target.is_dir():
        raise UpdateRejected("destination is not AIP-V451-PREVIEW")
    if not ((target / "src" / "aip").is_dir() and (target / "run_aip_ux_preview.cmd").is_file()):
        raise UpdateRejected("PREVIEW application signature missing")
    return target.resolve(strict=True)


def install(package_root: Path, target: Path, *, dry_run: bool = False) -> dict[str, object]:
    manifest, files = verify_payload(package_root.resolve())
    target = _validate_target(target)
    for relative, _ in files:
        destination = target / relative
        if destination.is_symlink() or any(
            parent.is_symlink()
            for parent in destination.parents
            if parent != target and target in parent.parents
        ):
            raise UpdateRejected("destination contains a symbolic link")
    count = len(files)
    if dry_run:
        return {"status": "verified_only", "files": count, "sha": manifest["source_sha"]}

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target / ".aip-preview-backups" / (now + "-" + manifest["source_sha"][:10])
    if backup.exists():
        raise UpdateRejected("backup directory exists; retry safely")
    backup.mkdir(parents=True)
    applied: list[tuple[Path, bool]] = []
    originals: list[str] = []
    try:
        for relative, source in files:
            dest = target / relative
            existed = dest.is_file()
            if dest.exists() and not existed:
                raise UpdateRejected("destination is not a regular file")
            if existed:
                snapshot = backup / relative
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, snapshot)
                originals.append(relative.as_posix())
            dest.parent.mkdir(parents=True, exist_ok=True)
            staging = dest.with_name(dest.name + ".aip-update-tmp")
            try:
                shutil.copyfile(source, staging)
                os.replace(staging, dest)
            finally:
                if staging.exists():
                    staging.unlink()
            applied.append((relative, existed))
        (backup / "RESTORE_MANIFEST.json").write_text(
            json.dumps(
                {
                    "source_sha": manifest["source_sha"],
                    "replaced": originals,
                    "new_files": [str(path) for path, existed in applied if not existed],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        for relative, existed in reversed(applied):
            dest = target / relative
            if existed:
                os.replace(backup / relative, dest)
            else:
                dest.unlink(missing_ok=True)
        raise
    return {
        "status": "applied",
        "files": count,
        "sha": manifest["source_sha"],
        "backup": str(backup),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AIP PREVIEW safe update")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--preview-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = install(args.package_root, args.preview_root, dry_run=args.dry_run)
    except (OSError, ValueError, UpdateRejected) as exc:
        # Do not print paths or exception messages from the institutional environment.
        print("ERROR: instalacion rechazada o fallida; PREVIEW y respaldos deben revisarse.")
        return 2
    print(f"AIP PREVIEW {result['status']}: {result['files']} archivos, SHA {result['sha']}")
    if result.get("backup"):
        print("Respaldo local creado en PREVIEW/.aip-preview-backups/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
