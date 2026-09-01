from __future__ import annotations

import argparse
import io
import os
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from checkpoint_contract import (
    CHECKPOINT_DIR,
    MARKER_NAME,
    CheckpointVerification,
    decode_checkpoint_payload,
    load_manifest,
    validated_archive_members,
    verify_checkpoint,
)


def _backup_src(root: Path) -> Path | None:
    source = root / "src"
    if not source.is_dir():
        return None

    backup_dir = root / "recovery" / "local_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"AIP_BEFORE_CHECKPOINT_RESTORE_{timestamp}.zip"

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


def _extract_to_staging(
    payload: bytes,
    root: Path,
) -> tuple[tempfile.TemporaryDirectory[str], Path, CheckpointVerification]:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = load_manifest(checkpoint_dir)

    temporary = tempfile.TemporaryDirectory(prefix=".aip-checkpoint-stage-", dir=root)
    stage_root = Path(temporary.name)
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            members, file_count = validated_archive_members(archive, manifest)
            for member in members:
                normalized = member.name.replace("\\", "/").rstrip("/")
                destination = stage_root.joinpath(*normalized.split("/"))
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Unable to read checkpoint member: {member.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)

                mode = member.mode & 0o777
                if mode:
                    try:
                        os.chmod(destination, mode)
                    except OSError:
                        pass

        staged_src = stage_root / "src"
        if not staged_src.is_dir():
            raise RuntimeError("Checkpoint staging did not produce a src tree")

        missing_critical = [
            item for item in manifest.critical_members if not (stage_root / item).is_file()
        ]
        if missing_critical:
            raise RuntimeError(
                "Staged checkpoint is missing critical runtime members: "
                + ", ".join(missing_critical)
            )

        verification = CheckpointVerification(
            digest=manifest.payload_sha256,
            part_count=manifest.part_count,
            archive_member_count=len(members),
            archive_file_count=file_count,
            critical_member_count=len(manifest.critical_members),
        )
        return temporary, staged_src, verification
    except Exception:
        temporary.cleanup()
        raise


def _replace_src_transactionally(root: Path, staged_src: Path) -> None:
    target = root / "src"
    previous = root / ".aip_src_before_checkpoint_restore"

    if previous.exists():
        shutil.rmtree(previous)

    had_existing = target.exists()
    if had_existing:
        target.rename(previous)

    try:
        staged_src.rename(target)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        if had_existing and previous.exists():
            previous.rename(target)
        raise
    else:
        if previous.exists():
            shutil.rmtree(previous)


def restore_checkpoint(
    root: Path,
    *,
    create_backup: bool = True,
) -> tuple[CheckpointVerification, Path | None]:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = load_manifest(checkpoint_dir)
    payload, digest = decode_checkpoint_payload(checkpoint_dir, manifest)

    # Full archive validation and staging happen before src is touched.
    temporary, staged_src, verification = _extract_to_staging(payload, root)
    backup: Path | None = None
    try:
        if create_backup:
            backup = _backup_src(root)
        _replace_src_transactionally(root, staged_src)
    finally:
        temporary.cleanup()

    marker_path = root / MARKER_NAME
    marker_path.write_text(digest + "\n", encoding="ascii")
    return verification, backup


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify or restore the canonical AIP Enterprise RC1 runtime checkpoint"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the canonical checkpoint without modifying src",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip the restore-level ZIP backup because an outer installer already created one",
    )
    return parser


def _print_verification(prefix: str, result: CheckpointVerification) -> None:
    print(f"{prefix}: {result.digest}")
    print(f"Validated checkpoint parts: {result.part_count}")
    print(f"Validated archive members: {result.archive_member_count}")
    print(f"Validated archive files: {result.archive_file_count}")
    print(f"Validated critical runtime members: {result.critical_member_count}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]

    if args.verify:
        result = verify_checkpoint(root)
        _print_verification("AIP canonical runtime checkpoint OK", result)
        return 0

    result, backup = restore_checkpoint(root, create_backup=not args.skip_backup)
    _print_verification("AIP canonical runtime checkpoint restored", result)
    print(f"Runtime marker written: {MARKER_NAME}")
    if backup is not None:
        print(f"Rollback backup retained: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
