from __future__ import annotations

import argparse
from pathlib import Path

from scripts.recovery.checkpoint_contract import CHECKPOINT_DIR, verify_checkpoint


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the certified AIP Enterprise RC1 runtime checkpoint."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing the recovery checkpoint.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root = args.root.resolve()
    verification = verify_checkpoint(root)

    print("AIP FINAL CHECKPOINT: PASS")
    print(f"checkpoint_dir={root / CHECKPOINT_DIR}")
    print(f"sha256={verification.digest}")
    print(f"parts={verification.part_count}")
    print(f"archive_members={verification.archive_member_count}")
    print(f"archive_files={verification.archive_file_count}")
    print(f"critical_members={verification.critical_member_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
