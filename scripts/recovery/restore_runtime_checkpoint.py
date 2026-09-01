from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-certified-src-20260829")
MANIFEST_NAME = "MANIFEST.json"
PART_GLOB = "runtime_src.part*.b64"
MARKER_NAME = ".aip_runtime_checkpoint.sha256"

CRITICAL_MEMBERS = {
    "src/aip/product/configured/services/configured_portfolio_var_service.py",
    "src/aip/product/configured/adapters/configured_market_provider.py",
    "src/aip/product/configured/adapters/configured_liquidity_provider.py",
    "src/aip/ui/modules/macro_intelligence/views/macro_intelligence_view.py",
    "src/aip/product/economic/economic_snapshot_store.py",
    "src/aip/ui/application/main.py",
    "src/aip/ui/application/app.py",
}


def _load_manifest(checkpoint_dir: Path) -> dict[str, Any]:
    manifest_path = checkpoint_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(f"Checkpoint manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Checkpoint manifest must be a JSON object")
    return payload


def _declared_parts(checkpoint_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    raw_parts = manifest.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise RuntimeError("Checkpoint manifest does not declare any parts")

    names: list[str] = []
    for item in raw_parts:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError("Checkpoint manifest contains an invalid part name")
        name = item.strip()
        path = Path(name)
        if path.name != name or path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe checkpoint part name: {name}")
        names.append(name)

    if len(names) != len(set(names)):
        raise RuntimeError("Checkpoint manifest contains duplicate part names")

    declared_count = manifest.get("part_count")
    if declared_count != len(names):
        raise RuntimeError(
            "Checkpoint part count mismatch in manifest: "
            f"declared {declared_count}, listed {len(names)}"
        )

    actual_names = {path.name for path in checkpoint_dir.glob(PART_GLOB)}
    expected_names = set(names)
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("undeclared=" + ",".join(extra))
        raise RuntimeError("Checkpoint part set mismatch: " + "; ".join(details))

    parts = [checkpoint_dir / name for name in names]
    for part in parts:
        if not part.is_file():
            raise RuntimeError(f"Checkpoint part is unavailable: {part}")
    return parts


def _decode_archive(parts: list[Path], manifest: dict[str, Any]) -> tuple[bytes, str]:
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    expected_encoded_chars = manifest.get("encoded_chars")
    if isinstance(expected_encoded_chars, int) and len(encoded) != expected_encoded_chars:
        raise RuntimeError(
            "Checkpoint base64 length mismatch: "
            f"expected {expected_encoded_chars}, got {len(encoded)}"
        )

    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError("Checkpoint base64 payload is invalid") from exc

    expected_bytes = manifest.get("archive_bytes")
    if isinstance(expected_bytes, int) and len(payload) != expected_bytes:
        raise RuntimeError(
            "Checkpoint archive size mismatch: "
            f"expected {expected_bytes}, got {len(payload)}"
        )

    expected_digest = manifest.get("archive_sha256")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise RuntimeError("Checkpoint manifest has an invalid archive SHA-256")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_digest:
        raise RuntimeError(
            "Checkpoint checksum mismatch: "
            f"expected {expected_digest}, got {digest}"
        )
    return payload, digest


def _expected_source_files(manifest: dict[str, Any]) -> dict[str, tuple[int, str]]:
    raw_files = manifest.get("source_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise RuntimeError("Checkpoint manifest does not declare source files")

    expected: dict[str, tuple[int, str]] = {}
    for item in raw_files:
        if not isinstance(item, dict):
            raise RuntimeError("Checkpoint manifest contains an invalid source file record")
        path = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(path, str)
            or not path.startswith("src/")
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise RuntimeError(f"Invalid source file record: {item!r}")
        normalized = path.replace("\\", "/")
        if normalized in expected:
            raise RuntimeError(f"Duplicate source file in manifest: {normalized}")
        expected[normalized] = (size, digest)

    declared_count = manifest.get("source_file_count")
    if declared_count != len(expected):
        raise RuntimeError(
            "Checkpoint source file count mismatch: "
            f"declared {declared_count}, listed {len(expected)}"
        )
    return expected


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    safe: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        normalized = member.name.replace("\\", "/")
        path = Path(normalized)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "src"
        ):
            raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise RuntimeError(f"Unsupported checkpoint member type: {member.name}")
        safe.append(member)
    return safe


def _verify_archive_files(
    archive: tarfile.TarFile,
    manifest: dict[str, Any],
) -> tuple[int, int]:
    expected = _expected_source_files(manifest)
    safe_members = _safe_members(archive)
    regular_members = {
        member.name.replace("\\", "/"): member
        for member in safe_members
        if member.isfile()
    }

    missing = sorted(set(expected) - set(regular_members))
    extra = sorted(set(regular_members) - set(expected))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing={len(missing)}")
        if extra:
            details.append(f"extra={len(extra)}")
        raise RuntimeError("Checkpoint source tree mismatch: " + "; ".join(details))

    for path, (expected_size, expected_digest) in expected.items():
        member = regular_members[path]
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"Unable to read checkpoint member: {path}")
        data = extracted.read()
        if len(data) != expected_size:
            raise RuntimeError(
                f"Checkpoint member size mismatch for {path}: "
                f"expected {expected_size}, got {len(data)}"
            )
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_digest:
            raise RuntimeError(
                f"Checkpoint member checksum mismatch for {path}: "
                f"expected {expected_digest}, got {digest}"
            )

    missing_critical = sorted(CRITICAL_MEMBERS - set(expected))
    if missing_critical:
        raise RuntimeError(
            "Certified checkpoint is missing critical runtime members: "
            + ", ".join(missing_critical)
        )
    return len(expected), len(CRITICAL_MEMBERS)


def verify_checkpoint(root: Path) -> tuple[str, int, int, int]:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = _load_manifest(checkpoint_dir)
    parts = _declared_parts(checkpoint_dir, manifest)
    payload, digest = _decode_archive(parts, manifest)

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        source_count, critical_count = _verify_archive_files(archive, manifest)

    return digest, len(parts), source_count, critical_count


def _restore(root: Path) -> tuple[str, int, int, int]:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = _load_manifest(checkpoint_dir)
    parts = _declared_parts(checkpoint_dir, manifest)
    payload, digest = _decode_archive(parts, manifest)

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        source_count, critical_count = _verify_archive_files(archive, manifest)
        archive.extractall(root, members=_safe_members(archive))

    marker_path = root / MARKER_NAME
    marker_path.write_text(digest + "\n", encoding="ascii")
    return digest, len(parts), source_count, critical_count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify or restore the certified AIP runtime checkpoint")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the certified checkpoint without modifying src",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]

    if args.verify:
        digest, part_count, source_count, critical_count = verify_checkpoint(root)
        print(f"AIP certified runtime checkpoint OK: {digest}")
    else:
        digest, part_count, source_count, critical_count = _restore(root)
        print(f"AIP certified runtime checkpoint restored: {digest}")
        print(f"Runtime marker written: {MARKER_NAME}")

    print(f"Validated checkpoint parts: {part_count}")
    print(f"Validated source files: {source_count}")
    print(f"Validated critical runtime members: {critical_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
