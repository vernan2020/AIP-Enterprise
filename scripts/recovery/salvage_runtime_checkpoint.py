from __future__ import annotations

import base64
import binascii
import hashlib
import io
import lzma
import tarfile
from pathlib import Path

from checkpoint_contract import (
    CHECKPOINT_DIR,
    PART_GLOB,
    declared_part_paths,
    load_manifest,
    normalize_base64_text,
)

MINIMUM_PYTHON_FILES = 750


def _decode(parts: tuple[Path, ...], expected_digest: str) -> tuple[bytes, str]:
    chunks: list[str] = []
    for part in parts:
        text = part.read_text(encoding="ascii")
        normalized = normalize_base64_text(text)
        if not normalized:
            raise RuntimeError(f"Checkpoint part is empty: {part}")
        chunks.append(normalized)
    try:
        payload = base64.b64decode("".join(chunks), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("Checkpoint base64 payload is invalid") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_digest:
        raise RuntimeError(
            f"Checkpoint checksum mismatch: expected {expected_digest}, got {digest}"
        )
    return payload, digest


def _safe_relative(name: str) -> Path:
    normalized = name.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "src":
        raise RuntimeError(f"Unsafe checkpoint member: {name}")
    return path


def _write_member(root: Path, archive: tarfile.TarFile, member: tarfile.TarInfo) -> bool:
    relative = _safe_relative(member.name)
    destination = root / relative
    if member.isdir():
        destination.mkdir(parents=True, exist_ok=True)
        return False
    if not member.isfile():
        raise RuntimeError(f"Unsupported checkpoint member type: {member.name}")
    source = archive.extractfile(member)
    if source is None:
        raise RuntimeError(f"Unable to read checkpoint member: {member.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read())
    return destination.suffix == ".py"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checkpoint_dir = root / CHECKPOINT_DIR
    manifest = load_manifest(checkpoint_dir)
    parts = declared_part_paths(checkpoint_dir, manifest)
    payload, digest = _decode(parts, manifest.payload_sha256)
    critical = set(manifest.critical_members)

    extracted: set[str] = set()
    python_files = 0
    corruption: str | None = None

    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r|*") as archive:
            while True:
                try:
                    member = archive.next()
                except (lzma.LZMAError, tarfile.ReadError, EOFError) as exc:
                    corruption = f"{type(exc).__name__}: {exc}"
                    break
                if member is None:
                    break
                try:
                    is_python = _write_member(root, archive, member)
                except (lzma.LZMAError, tarfile.ReadError, EOFError) as exc:
                    corruption = f"{type(exc).__name__}: {exc}"
                    break
                extracted.add(member.name.replace("\\", "/"))
                python_files += int(is_python)
    except (lzma.LZMAError, tarfile.ReadError, EOFError) as exc:
        corruption = f"{type(exc).__name__}: {exc}"

    missing_critical = sorted(item for item in critical if not (root / item).is_file())

    print(f"Verified checkpoint payload SHA-256: {digest}")
    print(f"Extracted members before corruption/end: {len(extracted)}")
    print(f"Extracted Python files: {python_files}")
    print(f"Critical members present: {len(critical) - len(missing_critical)}/{len(critical)}")
    print(f"Compression status: {corruption or 'stream completed without corruption'}")
    if missing_critical:
        print("Missing critical members: " + ", ".join(missing_critical))

    if missing_critical:
        raise RuntimeError(
            "Salvage is incomplete; critical runtime members are missing: "
            + ", ".join(missing_critical)
        )
    if python_files < MINIMUM_PYTHON_FILES:
        raise RuntimeError(
            f"Salvage extracted only {python_files} Python files; minimum is {MINIMUM_PYTHON_FILES}"
        )

    print(f"Validated critical members: {len(critical)}")
    print("Temporary salvage accepted for source materialization only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
