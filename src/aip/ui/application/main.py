from __future__ import annotations

import sys

from aip.ui.application.app import AIPApplication


def main(argv: list[str] | None = None) -> int:
    application = AIPApplication(argv or sys.argv)
    application.create_window()
    return application.exec()
