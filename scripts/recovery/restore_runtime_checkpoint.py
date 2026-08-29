from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

EXPECTED_SHA256 = "74bfaa04d2709ac903e4d315b46cf2c74e9aa62a7749286e0110c86fde11c6c4"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-20260829")
PART_PATTERN = "runtime_src.part*.b64"


def _safe_members(archive: tarfile.TarFile):
    for member in archive.getmembers():
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "src":
            raise RuntimeError(f"Unsafe checkpoint member: {member.name}")
        yield member


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checkpoint_dir = root / CHECKPOINT_DIR
    parts = sorted(checkpoint_dir.glob(PART_PATTERN))
    if not parts:
        raise RuntimeError(f"No runtime checkpoint parts found in {checkpoint_dir}")

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    payload = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Checkpoint checksum mismatch: {digest}")

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        archive.extractall(root, members=_safe_members(archive))

    print(f"AIP runtime checkpoint restored: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
