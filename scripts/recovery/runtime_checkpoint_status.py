from __future__ import annotations

import json
from pathlib import Path

CHECKPOINT_DIR = Path("recovery/checkpoints/rc1-final-20260829")
MANIFEST_NAME = "MANIFEST.json"
MARKER_NAME = ".aip_runtime_checkpoint.sha256"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / CHECKPOINT_DIR / MANIFEST_NAME
    marker_path = root / MARKER_NAME

    if not manifest_path.is_file():
        print("Runtime checkpoint status: MISSING_MANIFEST")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Runtime checkpoint status: INVALID_MANIFEST ({exc})")
        return 1

    expected = manifest.get("payload_sha256")
    critical = manifest.get("critical_members") or []
    if not isinstance(expected, str) or len(expected) != 64:
        print("Runtime checkpoint status: INVALID_DIGEST")
        return 1
    if not isinstance(critical, list) or not critical:
        print("Runtime checkpoint status: INVALID_CRITICAL_MEMBERS")
        return 1

    if not marker_path.is_file():
        print("Runtime checkpoint status: NOT_RESTORED")
        return 1

    actual = marker_path.read_text(encoding="ascii", errors="ignore").strip()
    if actual != expected:
        print("Runtime checkpoint status: STALE")
        return 1

    missing = [item for item in critical if not (root / item).is_file()]
    if missing:
        print("Runtime checkpoint status: INCOMPLETE")
        for item in missing:
            print(f" - missing: {item}")
        return 1

    print(f"Runtime checkpoint status: CERTIFIED ({expected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
