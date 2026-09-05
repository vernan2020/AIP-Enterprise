from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from hashlib import sha256
from pathlib import Path

PACKAGE_DIR_NAME = "AIP_RC1_CERTIFIED"
PAYLOAD_DIR_NAME = "payload"
MANIFEST_NAME = "manifest.json"
CERTIFIED_MARKER_NAME = ".aip_certified_runtime.json"

ROLLBACK_TARGETS = (
    Path("src"),
    Path("run_aip_configured.cmd"),
    Path("scripts/recovery"),
    Path("recovery/checkpoints/rc1-final-20260829"),
    Path("config/runtime.local.cmd.example"),
)


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
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in ROLLBACK_TARGETS:
            source = project_root / relative
            if source.is_file():
                archive.write(source, relative.as_posix())
            elif source.is_dir():
                for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
                    archive.write(
                        file_path,
                        file_path.relative_to(project_root).as_posix(),
                    )
    return backup_path


def _remove_path(path: Path) -> None:
    """Best-effort removal that handles ordinary Windows read-only attributes."""
    if not path.exists() and not path.is_symlink():
        return
    try:
        if path.is_dir() and not path.is_symlink():
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

    if path.is_dir() and not path.is_symlink():

        def _onerror(function, filename, _exc_info):  # type: ignore[no-untyped-def]
            try:
                os.chmod(filename, 0o700)
                function(filename)
            except OSError:
                raise

        shutil.rmtree(path, onerror=_onerror)
    else:
        path.unlink()


def _restore_backup(project_root: Path, backup_path: Path) -> None:
    """Restore every recovery-owned target to its exact pre-install state."""
    for relative in ROLLBACK_TARGETS:
        target = project_root / relative
        if target.exists() or target.is_symlink():
            _remove_path(target)

    marker = project_root / CERTIFIED_MARKER_NAME
    if marker.exists() or marker.is_symlink():
        _remove_path(marker)

    with zipfile.ZipFile(backup_path, "r") as archive:
        for info in archive.infolist():
            candidate = Path(info.filename)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise RuntimeError(f"Unsafe rollback archive member: {info.filename}")
        archive.extractall(project_root)


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


def _relative_files(tree: Path) -> set[Path]:
    return {path.relative_to(tree) for path in tree.rglob("*") if path.is_file()}


def _snapshot_src(target: Path, snapshot: Path) -> None:
    if snapshot.exists() or snapshot.is_symlink():
        _remove_path(snapshot)
    if target.is_dir():
        shutil.copytree(target, snapshot, copy_function=shutil.copy2)


def _copy_file_replace(source: Path, destination: Path) -> None:
    """Replace one file safely, with a Windows ACL-compatible fallback."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".aip-certified-new")
    if temporary.exists() or temporary.is_symlink():
        _remove_path(temporary)
    shutil.copy2(source, temporary)
    try:
        try:
            os.replace(temporary, destination)
        except PermissionError:
            # Some Windows directory ACLs deny delete/rename while still allowing
            # writes. The outer ZIP backup preserves complete rollback semantics.
            shutil.copy2(temporary, destination)
            temporary.unlink()
    finally:
        if temporary.exists() or temporary.is_symlink():
            _remove_path(temporary)


def _synchronize_tree(source: Path, target: Path) -> None:
    """Make target match source without renaming the live target directory."""
    target.mkdir(parents=True, exist_ok=True)
    expected_files = _relative_files(source)

    for relative in sorted(expected_files, key=lambda item: item.as_posix().casefold()):
        _copy_file_replace(source / relative, target / relative)

    existing_files = [path for path in target.rglob("*") if path.is_file()]
    for path in existing_files:
        relative = path.relative_to(target)
        if relative not in expected_files:
            _remove_path(path)

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


def _replace_src_transactionally(payload_root: Path, project_root: Path) -> None:
    """Install certified src without renaming the live Windows directory.

    A validated payload is copied into the existing ``src`` tree file-by-file.
    A private snapshot provides immediate src-level rollback, while the outer ZIP
    backup remains authoritative for the complete installer transaction.
    """
    incoming_src = payload_root / "src"
    if not incoming_src.is_dir():
        raise RuntimeError("Certified payload does not contain src")

    existing_src = project_root / "src"
    previous = project_root / ".aip_src_before_certified"
    had_existing = existing_src.is_dir()

    if had_existing:
        _snapshot_src(existing_src, previous)
    elif previous.exists() or previous.is_symlink():
        _remove_path(previous)

    try:
        _synchronize_tree(incoming_src, existing_src)
    except Exception as install_error:
        if had_existing and previous.is_dir():
            try:
                _synchronize_tree(previous, existing_src)
            except Exception as rollback_error:
                raise RuntimeError(
                    "Certified src installation failed and src rollback also failed. "
                    f"install={install_error}; rollback={rollback_error}"
                ) from install_error
        elif existing_src.exists() or existing_src.is_symlink():
            _remove_path(existing_src)
        raise
    else:
        if previous.exists() or previous.is_symlink():
            _remove_path(previous)


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
            raise RuntimeError("Post-install validation failed: " + " ".join(command))


def _write_install_marker(project_root: Path, manifest: dict) -> None:
    marker = project_root / CERTIFIED_MARKER_NAME
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
        _run_validation(project_root)
        _write_install_marker(project_root, manifest)
    except Exception as exc:
        print(f"RECOVERY FAILED: {exc}", file=sys.stderr)
        try:
            _restore_backup(project_root, backup_path)
        except Exception as rollback_exc:
            print(
                f"AUTOMATIC ROLLBACK FAILED: {rollback_exc}",
                file=sys.stderr,
            )
            print(
                f"Manual rollback backup preserved at: {backup_path}",
                file=sys.stderr,
            )
            return 2
        print("Automatic rollback: PASS", file=sys.stderr)
        print(f"Project restored from: {backup_path.name}", file=sys.stderr)
        return 1

    print("AIP certified runtime installed successfully.")
    print(f"Rollback backup preserved at: {backup_path.name}")
    print("Next step: run run_aip_configured.cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
