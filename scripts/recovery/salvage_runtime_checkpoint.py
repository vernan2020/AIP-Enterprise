from __future__ import annotations

import base64
import hashlib
import io
import json
import lzma
import tarfile
from pathlib import Path
from typing import Any

CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_NAME = "MANIFEST.json"
PART_GLOB = "runtime_final.part*.b64"
MINIMUM_PYTHON_FILES = 750


def _load_manifest(checkpoint_dir: Path) -> dict[str, Any]:
    manifest_path = checkpoint_dir / MANIFEST_NAME
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Checkpoint manifest must be a JSON object")
    return payload


def _parts(checkpoint_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    raw = manifest.get("parts")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Checkpoint manifest does not declare parts")
    names = [str(item).strip() for item in raw]
    if len(names) != len(set(names)):
        raise RuntimeError("Checkpoint manifest contains duplicate parts")
    actual = {path.name for path in checkpoint_dir.glob(PART_GLOB)}
    if actual != set(names):
        raise RuntimeError("Checkpoint part set does not match the manifest")
    return [checkpoint_dir / name for name in names]


def _decode(parts: list[Path], manifest: dict[str, Any]) -> tuple[bytes, str]:
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(payload).hexdigest()
    expected = str(manifest.get("payload_sha256", ""))
    if digest != expected:
        raise RuntimeError(f"Checkpoint checksum mismatch: expected {expected}, got {digest}")
    return payload, digest


def _critical(manifest: dict[str, Any]) -> set[str]:
    raw = manifest.get("critical_members")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Checkpoint does not declare critical members")
    result = {str(item).replace("\\", "/") for item in raw}
    if any(not item.startswith("src/") for item in result):
        raise RuntimeError("Invalid critical member declaration")
    return result


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
    manifest = _load_manifest(checkpoint_dir)
    parts = _parts(checkpoint_dir, manifest)
    payload, digest = _decode(parts, manifest)
    critical = _critical(manifest)

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

    # Emit forensic metrics before enforcing acceptance criteria.  These
    # diagnostics are required to decide whether the damaged transport can
    # be used as a temporary source-recovery aid; they do not weaken any
    # acceptance criterion below.
    print(f"Verified corrupt checkpoint payload SHA-256: {digest}")
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
