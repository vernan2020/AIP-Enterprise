from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

EXPECTED_SHA256 = "d88798ab1ccc83742fd6e62dccbf07d86d3b4e85d7a9bb9ee78161665d05e373"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
PART_PATTERN = "runtime_final.part*.b64"


def _safe_members(archive: tarfile.TarFile):
    for member in archive.getmembers():
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "src":
            raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
        yield member


def _ordered_parts(checkpoint_dir: Path) -> list[Path]:
    parts = sorted(checkpoint_dir.glob(PART_PATTERN), key=lambda item: item.name)
    if not parts:
        raise RuntimeError(f"No runtime checkpoint parts found in {checkpoint_dir}")
    return parts


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checkpoint_dir = root / CHECKPOINT_DIR
    parts = _ordered_parts(checkpoint_dir)

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            "Checkpoint checksum mismatch: "
            f"expected {EXPECTED_SHA256}, got {digest}"
        )

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        archive.extractall(root, members=_safe_members(archive))

    print(f"AIP runtime checkpoint restored: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
