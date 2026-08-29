from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

EXPECTED_SHA256 = "5c245fb32d1d0977e637bca5263c25fe519c6dc6bd109ae98823c5c31b2120ae"
CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
PART_PATTERN = "runtime_final.part*.b64"
CRITICAL_MEMBERS = {
    "src/aip/product/configured/services/configured_portfolio_var_service.py",
    "src/aip/product/configured/adapters/configured_market_provider.py",
    "src/aip/product/configured/adapters/configured_liquidity_provider.py",
    "src/aip/ui/modules/macro_intelligence/views/macro_intelligence_view.py",
    "src/aip/product/economic/economic_snapshot_store.py",
}


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
        members = archive.getmembers()
        names = {member.name.replace("\\", "/") for member in members}
        missing = sorted(CRITICAL_MEMBERS - names)
        if missing:
            raise RuntimeError(
                "Checkpoint is structurally incomplete; critical members missing: "
                + ", ".join(missing)
            )
        archive.extractall(root, members=_safe_members(archive))

    print(f"AIP runtime checkpoint restored: {digest}")
    print(f"Validated critical runtime members: {len(CRITICAL_MEMBERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
