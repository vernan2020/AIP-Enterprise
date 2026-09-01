from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_NAME = "MANIFEST.json"
PART_GLOB = "runtime_final.part*.b64"
MARKER_NAME = ".aip_runtime_checkpoint.sha256"


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


def _decode_payload(parts: list[Path], manifest: dict[str, Any]) -> bytes:
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError("Checkpoint base64 payload is invalid") from exc

    expected_digest = manifest.get("payload_sha256")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise RuntimeError("Checkpoint manifest has an invalid SHA-256")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_digest:
        raise RuntimeError(
            "Checkpoint checksum mismatch: "
            f"expected {expected_digest}, got {digest}"
        )
    return payload


def _safe_members(archive: tarfile.TarFile):
    for member in archive.getmembers():
        path = Path(member.name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "src"
        ):
            raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
        yield member


def _critical_members(manifest: dict[str, Any]) -> set[str]:
    raw = manifest.get("critical_members")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Checkpoint manifest does not declare critical members")
    members: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or not item.startswith("src/"):
            raise RuntimeError(f"Invalid critical checkpoint member: {item!r}")
        members.add(item.replace("\\", "/"))
    return members


def verify_checkpoint(root: Path) -> tuple[str, int, int]:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = _load_manifest(checkpoint_dir)
    parts = _declared_parts(checkpoint_dir, manifest)
    payload = _decode_payload(parts, manifest)
    digest = hashlib.sha256(payload).hexdigest()

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        names = {member.name.replace("\\", "/") for member in archive.getmembers()}
        critical = _critical_members(manifest)
        missing = sorted(critical - names)
        if missing:
            raise RuntimeError(
                "Checkpoint is structurally incomplete; critical members missing: "
                + ", ".join(missing)
            )
        list(_safe_members(archive))

    return digest, len(parts), len(critical)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = _load_manifest(checkpoint_dir)
    parts = _declared_parts(checkpoint_dir, manifest)
    payload = _decode_payload(parts, manifest)
    digest = hashlib.sha256(payload).hexdigest()
    critical = _critical_members(manifest)

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        names = {member.name.replace("\\", "/") for member in archive.getmembers()}
        missing = sorted(critical - names)
        if missing:
            raise RuntimeError(
                "Checkpoint is structurally incomplete; critical members missing: "
                + ", ".join(missing)
            )
        archive.extractall(root, members=_safe_members(archive))

    marker_path = root / MARKER_NAME
    marker_path.write_text(digest + "\n", encoding="ascii")

    print(f"AIP runtime checkpoint restored: {digest}")
    print(f"Validated checkpoint parts: {len(parts)}")
    print(f"Validated critical runtime members: {len(critical)}")
    print(f"Runtime marker written: {marker_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
