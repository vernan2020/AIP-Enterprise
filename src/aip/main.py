from __future__ import annotations

import os

from aip.core.startup_timing import StartupTimer


def _run_configured_preflight() -> int:
    """Validate configured runtime before importing the desktop UI."""

    if os.getenv("AIP_EXECUTION_MODE", "").strip().upper() != "CONFIGURED":
        return 0

    from aip.tools.preflight_runtime import main as _preflight

    return _preflight([])


def main(argv: list[str] | None = None) -> int:
    """Launch the canonical RC1 desktop shell for production startup."""

    startup_timer = StartupTimer()
    with startup_timer.stage("configured_preflight"):
        preflight_status = _run_configured_preflight()
    if preflight_status:
        return preflight_status

    # Import the Qt application only after the fast configured preflight. This
    # keeps validation cheap and makes the UI import cost independently visible.
    with startup_timer.stage("desktop_ui_import"):
        from aip.ui.application.main import main as _launch_rc1_application

    return _launch_rc1_application(argv, startup_timer=startup_timer)


if __name__ == "__main__":
    raise SystemExit(main())
