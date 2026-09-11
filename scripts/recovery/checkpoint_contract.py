from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_VERSION = "aip-runtime-checkpoint-v1"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_NAME = "MANIFEST.json"
PART_GLOB = "runtime_final.part*.b64"
MARKER_NAME = ".aip_runtime_checkpoint.sha256"

_PART_NAME_RE = re.compile(r"^runtime_final\.part[0-9A-Za-z-]+\.b64$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CheckpointManifest:
    checkpoint: str
    checkpoint_directory: str
    payload_sha256: str
    encoding: str
    archive_detection: str
    part_count: int
    parts: tuple[str, ...]
    critical_members: tuple[str, ...]
    runtime_guarantees: tuple[str, ...]
    qa: dict[str, Any]
    contract_version: str


@dataclass(frozen=True, slots=True)
class CheckpointVerification:
    digest: str
    part_count: int
    archive_member_count: int
    archive_file_count: int
    critical_member_count: int


def normalize_base64_text(value: str) -> str:
    """Remove transport whitespace before strict Base64 validation."""
    return "".join(value.split())


def decode_github_contents_base64(value: str, *, label: str) -> bytes:
    """Decode a GitHub Contents API ``content`` field safely.

    GitHub may wrap the Base64 text with line breaks. Whitespace is normalized
    first, then strict Base64 validation is applied.
    """
    normalized = normalize_base64_text(value)
    if not normalized:
        raise RuntimeError(f"GitHub returned empty base64 content for {label}")
    try:
        return base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError(f"GitHub returned invalid base64 content for {label}") from exc


def _safe_part_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Checkpoint manifest contains an invalid part name")
    name = value.strip()
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise RuntimeError(f"Unsafe checkpoint part name: {name}")
    if not _PART_NAME_RE.fullmatch(name):
        raise RuntimeError(f"Unexpected checkpoint part name: {name}")
    return name


def _safe_src_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Invalid {label}: {value!r}")
    normalized = value.strip().replace("\\", "/")
    raw_parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise RuntimeError(f"Unsafe {label}: {value}")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or path.parts[0] != "src":
        raise RuntimeError(f"Unsafe {label}: {value}")
    if ":" in path.parts[0]:
        raise RuntimeError(f"Unsafe {label}: {value}")
    return path.as_posix()


def parse_manifest(payload: dict[str, Any]) -> CheckpointManifest:
    if not isinstance(payload, dict):
        raise RuntimeError("Checkpoint manifest must be a JSON object")

    contract_version = payload.get("contract_version")
    if contract_version != CONTRACT_VERSION:
        raise RuntimeError(
            "Unsupported checkpoint contract version: "
            f"expected {CONTRACT_VERSION}, got {contract_version!r}"
        )

    checkpoint = payload.get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        raise RuntimeError("Checkpoint manifest has an invalid checkpoint label")

    checkpoint_directory = payload.get("checkpoint_directory")
    expected_directory = CHECKPOINT_DIR.as_posix()
    if checkpoint_directory != expected_directory:
        raise RuntimeError(
            "Checkpoint manifest directory mismatch: "
            f"expected {expected_directory}, got {checkpoint_directory!r}"
        )

    if payload.get("encoding") != "base64":
        raise RuntimeError("Checkpoint manifest encoding must be base64")
    if payload.get("archive_detection") != "tarfile r:*":
        raise RuntimeError("Checkpoint manifest archive_detection must be 'tarfile r:*'")

    digest = payload.get("payload_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise RuntimeError("Checkpoint manifest has an invalid payload SHA-256")

    raw_parts = payload.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise RuntimeError("Checkpoint manifest does not declare any parts")
    parts = tuple(_safe_part_name(item) for item in raw_parts)
    if len(parts) != len(set(parts)):
        raise RuntimeError("Checkpoint manifest contains duplicate part names")

    declared_count = payload.get("part_count")
    if isinstance(declared_count, bool) or not isinstance(declared_count, int):
        raise RuntimeError("Checkpoint manifest part_count must be an integer")
    if declared_count <= 0 or declared_count != len(parts):
        raise RuntimeError(
            "Checkpoint part count mismatch in manifest: "
            f"declared {declared_count}, listed {len(parts)}"
        )

    raw_critical = payload.get("critical_members")
    if not isinstance(raw_critical, list) or not raw_critical:
        raise RuntimeError("Checkpoint manifest does not declare critical members")
    critical = tuple(
        _safe_src_path(item, label="critical member") for item in raw_critical
    )
    critical_casefold = [item.casefold() for item in critical]
    if len(critical_casefold) != len(set(critical_casefold)):
        raise RuntimeError("Checkpoint manifest contains duplicate critical members")

    raw_guarantees = payload.get("runtime_guarantees")
    if not isinstance(raw_guarantees, list) or not raw_guarantees:
        raise RuntimeError("Checkpoint manifest does not declare runtime guarantees")
    if any(not isinstance(item, str) or not item.strip() for item in raw_guarantees):
        raise RuntimeError("Checkpoint manifest contains an invalid runtime guarantee")

    qa = payload.get("qa")
    if not isinstance(qa, dict) or not qa:
        raise RuntimeError("Checkpoint manifest does not declare QA evidence")

    return CheckpointManifest(
        checkpoint=checkpoint.strip(),
        checkpoint_directory=checkpoint_directory,
        payload_sha256=digest,
        encoding="base64",
        archive_detection="tarfile r:*",
        part_count=declared_count,
        parts=parts,
        critical_members=critical,
        runtime_guarantees=tuple(item.strip() for item in raw_guarantees),
        qa=dict(qa),
        contract_version=contract_version,
    )


def load_manifest(checkpoint_dir: Path) -> CheckpointManifest:
    manifest_path = checkpoint_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(f"Checkpoint manifest not found: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Checkpoint manifest is unreadable: {manifest_path}") from exc
    return parse_manifest(payload)


def declared_part_paths(
    checkpoint_dir: Path,
    manifest: CheckpointManifest,
) -> tuple[Path, ...]:
    expected_names = set(manifest.parts)
    actual_names = {path.name for path in checkpoint_dir.glob(PART_GLOB)}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("undeclared=" + ",".join(extra))
        raise RuntimeError("Checkpoint part set mismatch: " + "; ".join(details))

    parts = tuple(checkpoint_dir / name for name in manifest.parts)
    unavailable = [str(path) for path in parts if not path.is_file()]
    if unavailable:
        raise RuntimeError("Checkpoint parts are unavailable: " + ", ".join(unavailable))
    return parts


def decode_checkpoint_payload(
    checkpoint_dir: Path,
    manifest: CheckpointManifest,
) -> tuple[bytes, str]:
    parts = declared_part_paths(checkpoint_dir, manifest)
    chunks: list[str] = []
    for part in parts:
        try:
            text = part.read_text(encoding="ascii")
        except (OSError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"Checkpoint part is unreadable: {part}") from exc
        normalized = normalize_base64_text(text)
        if not normalized:
            raise RuntimeError(f"Checkpoint part is empty: {part}")
        chunks.append(normalized)

    encoded = "".join(chunks)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("Checkpoint base64 payload is invalid") from exc

    digest = hashlib.sha256(payload).hexdigest()
    if digest != manifest.payload_sha256:
        raise RuntimeError(
            "Checkpoint checksum mismatch: "
            f"expected {manifest.payload_sha256}, got {digest}"
        )
    return payload, digest


def _normalized_archive_member(member: tarfile.TarInfo) -> str:
    normalized = member.name.replace("\\", "/")
    if member.isdir():
        normalized = normalized.rstrip("/")
    raw_parts = normalized.split("/") if normalized else []
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
    path = PurePosixPath(normalized)
    if path.is_absolute() or path.parts[0] != "src" or ":" in path.parts[0]:
        raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
    if not (member.isdir() or member.isfile()):
        raise RuntimeError(f"Unsupported checkpoint member type: {member.name}")
    return path.as_posix()


def validated_archive_members(
    archive: tarfile.TarFile,
    manifest: CheckpointManifest,
) -> tuple[tuple[tarfile.TarInfo, ...], int]:
    safe: list[tarfile.TarInfo] = []
    file_names: set[str] = set()
    seen_casefold: set[str] = set()

    for member in archive.getmembers():
        normalized = _normalized_archive_member(member)
        folded = normalized.casefold()
        if folded in seen_casefold:
            raise RuntimeError(f"Duplicate checkpoint archive member: {normalized}")
        seen_casefold.add(folded)
        safe.append(member)
        if member.isfile():
            file_names.add(normalized)

    missing_critical = sorted(set(manifest.critical_members) - file_names)
    if missing_critical:
        raise RuntimeError(
            "Certified checkpoint is missing critical runtime members: "
            + ", ".join(missing_critical)
        )
    if not file_names:
        raise RuntimeError("Checkpoint archive contains no files")
    return tuple(safe), len(file_names)


def verify_checkpoint(root: Path) -> CheckpointVerification:
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = load_manifest(checkpoint_dir)
    payload, digest = decode_checkpoint_payload(checkpoint_dir, manifest)

    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            members, file_count = validated_archive_members(archive, manifest)
    except (tarfile.TarError, OSError) as exc:
        raise RuntimeError("Checkpoint archive is invalid or unreadable") from exc

    return CheckpointVerification(
        digest=digest,
        part_count=manifest.part_count,
        archive_member_count=len(members),
        archive_file_count=file_count,
        critical_member_count=len(manifest.critical_members),
    )
