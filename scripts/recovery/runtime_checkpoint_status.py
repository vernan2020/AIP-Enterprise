from __future__ import annotations

import argparse
from pathlib import Path

from checkpoint_contract import CHECKPOINT_DIR, MARKER_NAME, load_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report AIP RC1 runtime checkpoint status")
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Return success when all manifest-declared critical runtime files exist locally",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    checkpoint_dir = root / CHECKPOINT_DIR
    marker_path = root / MARKER_NAME

    try:
        manifest = load_manifest(checkpoint_dir)
    except Exception as exc:
        print(f"Runtime checkpoint status: INVALID_OR_MISSING_MANIFEST ({exc})")
        return 2

    missing = [item for item in manifest.critical_members if not (root / item).is_file()]
    if missing:
        print("Runtime checkpoint status: INCOMPLETE")
        for item in missing:
            print(f" - missing: {item}")
        return 1

    if args.critical_only:
        print(
            "Runtime checkpoint critical members: PRESENT "
            f"({len(manifest.critical_members)}/{len(manifest.critical_members)})"
        )
        return 0

    if not marker_path.is_file():
        print("Runtime checkpoint status: PRESENT_NOT_MARKED")
        return 1

    actual = marker_path.read_text(encoding="ascii", errors="ignore").strip()
    if actual != manifest.payload_sha256:
        print("Runtime checkpoint status: STALE")
        print(f" - expected: {manifest.payload_sha256}")
        print(f" - marker:   {actual or '<empty>'}")
        return 1

    print(f"Runtime checkpoint status: CERTIFIED ({manifest.payload_sha256})")
    print(f"Critical members: {len(manifest.critical_members)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
