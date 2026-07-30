from __future__ import annotations

from aip.ui.application.main import main as _launch_rc1_application


def main(argv: list[str] | None = None) -> int:
    """Launch the canonical RC1 desktop shell for production startup."""
    return _launch_rc1_application(argv)


if __name__ == "__main__":
    raise SystemExit(main())
