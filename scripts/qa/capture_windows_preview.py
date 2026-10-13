"""Open V4.5.1 financial workspaces and capture genuine Qt screenshots on Windows.

The workflow uses DEMO sources and never accesses institutional credentials.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")
os.environ["AIP_EXECUTION_MODE"] = "DEMO"
os.environ["AIP_DEMO_MODE_ENABLED"] = "true"
os.environ["AIP_VECTOR_ENABLED"] = "false"
os.environ["AIP_FOLDERWATCH_ENABLED"] = "false"
os.environ["AIP_SQLSERVER_ENABLED"] = "false"
os.environ["AIP_BCCR_ENABLED"] = "false"

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from aip.ui.shell.intelligence_main_window import (  # noqa: E402
    FinancialIntelligenceMainWindow,
)

WORKSPACES = (
    ("financial_analysis", "01-analisis-financiero", 1),
    ("macro_intelligence", "02-inteligencia-macroeconomica", 3),
    ("price_risk", "03-riesgo-de-precio", 2),
)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont("Segoe UI", 9))
    print(
        f"Qt platform={os.environ['QT_QPA_PLATFORM']}; "
        f"font={app.font().family()}; available_fonts={len(QFontDatabase.families())}",
        flush=True,
    )
    output = Path("preview-screenshots")
    output.mkdir(exist_ok=True)
    window = FinancialIntelligenceMainWindow()
    try:
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        for route_id, filename, minimum_exports in WORKSPACES:
            window.open_workspace(route_id)
            app.processEvents()
            workspace = window.workspace.currentWidget()
            if workspace is None:
                raise RuntimeError(f"Empty workspace for {route_id}")
            exports = [
                button for button in workspace.findChildren(QPushButton)
                if button.text() == "Exportar CSV"
            ]
            if len(exports) < minimum_exports:
                raise AssertionError(
                    f"{route_id}: expected {minimum_exports} exports, found {len(exports)}"
                )
            capture = window.grab()
            if capture.isNull():
                raise RuntimeError(f"Empty Qt screenshot for {route_id}")
            destination = output / f"{filename}.png"
            if not capture.save(str(destination), "PNG"):
                raise OSError(f"Could not save screenshot: {destination}")
            print(f"PASS {route_id}: {len(exports)} export buttons; {destination}", flush=True)
        return 0
    finally:
        print("Closing Qt workspaces...", flush=True)
        for index in reversed(range(window.workspace.count())):
            widget = window.workspace.widget(index)
            if widget is not None:
                widget.close()
        QThreadPool.globalInstance().waitForDone(15000)
        window.close()
        app.processEvents()
        print("Qt workspaces closed", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
