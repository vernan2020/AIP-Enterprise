from __future__ import annotations

import os


def _run_configured_preflight() -> int:
    """Validate configured runtime before importing the desktop UI."""

    if os.getenv("AIP_EXECUTION_MODE", "").strip().upper() != "CONFIGURED":
        return 0

    from aip.tools.preflight_runtime import main as _preflight

    return _preflight([])


def main(argv: list[str] | None = None) -> int:
    """Launch the canonical RC1 desktop shell for production startup."""

    preflight_status = _run_configured_preflight()
    if preflight_status:
        return preflight_status

    # Import the Qt application only after the fast configured preflight. This
    # keeps validation cheap and avoids paying UI import cost in a second Python
    # process before the real application starts.
    from aip.ui.application.main import main as _launch_rc1_application

    return _launch_rc1_application(argv)


if __name__ == "__main__":
    raise SystemExit(main())
