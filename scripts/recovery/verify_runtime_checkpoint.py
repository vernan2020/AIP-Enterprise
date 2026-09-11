from __future__ import annotations

from pathlib import Path

from checkpoint_contract import verify_checkpoint


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    result = verify_checkpoint(root)
    print("AIP RUNTIME CHECKPOINT VERIFICATION")
    print(f"SHA-256: {result.digest}")
    print(f"Parts: {result.part_count}")
    print(f"Archive members: {result.archive_member_count}")
    print(f"Archive files: {result.archive_file_count}")
    print(f"Critical members: {result.critical_member_count}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
