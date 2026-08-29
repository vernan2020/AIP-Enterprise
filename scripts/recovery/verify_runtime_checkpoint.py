from __future__ import annotations

from pathlib import Path

from scripts.recovery.restore_runtime_checkpoint import verify_checkpoint


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    digest, part_count, critical_count = verify_checkpoint(root)
    print("AIP RUNTIME CHECKPOINT VERIFICATION")
    print(f"SHA-256: {digest}")
    print(f"Parts: {part_count}")
    print(f"Critical members: {critical_count}")
    print("Status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
