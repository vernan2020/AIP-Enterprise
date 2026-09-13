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


_TRANSIENT_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_TRANSIENT_SUFFIXES = {".pyc", ".pyo"}


def _backup_src(root: Path) -> Path | None:
    source = root / "src"
    if not source.is_dir():
        return None

    backup_dir = root / "recovery" / "local_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"AIP_BEFORE_CHECKPOINT_RESTORE_{timestamp}.zip"

    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in _TRANSIENT_NAMES for part in relative.parts):
                continue
            if path.suffix.lower() in _TRANSIENT_SUFFIXES:
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


def _remove_path(path: Path) -> None:
    """Best-effort removal that handles ordinary Windows read-only attributes."""
    if not path.exists():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return
    except PermissionError:
        pass

    try:
        os.chmod(path, 0o700)
    except OSError:
        pass

    if path.is_dir():
        def _onerror(function, filename, _exc_info):  # type: ignore[no-untyped-def]
            try:
                os.chmod(filename, 0o700)
                function(filename)
            except OSError:
                raise

        shutil.rmtree(path, onerror=_onerror)
    else:
        path.unlink()


def _snapshot_src(target: Path, snapshot: Path) -> None:
    if snapshot.exists():
        _remove_path(snapshot)
    if target.is_dir():
        shutil.copytree(target, snapshot, copy_function=shutil.copy2)


def _relative_files(tree: Path) -> set[Path]:
    return {
        path.relative_to(tree)
        for path in tree.rglob("*")
        if path.is_file()
        and not any(part in _TRANSIENT_NAMES for part in path.relative_to(tree).parts)
        and path.suffix.lower() not in _TRANSIENT_SUFFIXES
    }


def _copy_file_replace(source: Path, destination: Path) -> None:
    """Replace one file safely, with a Windows ACL-compatible fallback."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".aip-restore-new")
    if temporary.exists():
        _remove_path(temporary)
    shutil.copy2(source, temporary)
    try:
        try:
            os.replace(temporary, destination)
        except PermissionError:
            # Some Windows directory ACLs deny delete/rename while still allowing
            # writes. The pre-restore snapshot preserves rollback semantics.
            shutil.copy2(temporary, destination)
            temporary.unlink()
    finally:
        if temporary.exists():
            _remove_path(temporary)


def _synchronize_tree(source: Path, target: Path) -> None:
    """Make target match source without renaming the target directory itself."""
    target.mkdir(parents=True, exist_ok=True)
    expected_files = _relative_files(source)

    # Install/replace every certified file first. The fully validated source tree
    # already exists in staging, so no unverified bytes reach the live runtime.
    for relative in sorted(expected_files, key=lambda item: item.as_posix().casefold()):
        _copy_file_replace(source / relative, target / relative)

    # Remove files that do not belong to the certified checkpoint, including
    # interpreter caches that could otherwise retain stale modules.
    existing_files = [path for path in target.rglob("*") if path.is_file()]
    for path in existing_files:
        relative = path.relative_to(target)
        if relative not in expected_files:
            _remove_path(path)

    # Remove empty directories left by stale modules, deepest first. Never rename
    # or replace the live src directory itself; this is the Windows-safe invariant.
    directories = sorted(
        (path for path in target.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def _replace_src_transactionally(root: Path, staged_src: Path) -> None:
    """Install staged src with a local snapshot and automatic rollback.

    Windows can reject a rename of the live ``src`` directory even when all files
    within it are readable/writable (for example because of ACLs, antivirus, or a
    transient directory handle). Therefore transactionality is implemented as:

    1. copy the existing src to a private snapshot;
    2. synchronize the fully validated staged tree into live src;
    3. on any failure, synchronize the snapshot back;
    4. remove the snapshot only after success.

    This preserves rollback while avoiding a top-level directory rename.
    """
    target = root / "src"
    previous = root / ".aip_src_before_checkpoint_restore"
    had_existing = target.is_dir()

    if had_existing:
        _snapshot_src(target, previous)

    try:
        _synchronize_tree(staged_src, target)
    except Exception as install_error:
        if had_existing and previous.is_dir():
            try:
                _synchronize_tree(previous, target)
            except Exception as rollback_error:
                raise RuntimeError(
                    "Certified runtime installation failed and automatic src rollback "
                    f"also failed. install={install_error}; rollback={rollback_error}"
                ) from install_error
        elif target.exists():
            _remove_path(target)
        raise
    else:
        if previous.exists():
            _remove_path(previous)


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
