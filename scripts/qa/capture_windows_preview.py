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
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QPushButton,
    QScrollArea,
    QTabWidget,
)

from aip.ui.shell.intelligence_main_window import (  # noqa: E402
    FinancialIntelligenceMainWindow,
)

WORKSPACES = (
    ("financial_analysis", "01-analisis-financiero", 1),
    ("macro_intelligence", "02-inteligencia-macroeconomica", 3),
    ("price_risk", "03-riesgo-de-precio", 2),
)


def _capture(window: FinancialIntelligenceMainWindow, path: Path) -> None:
    image = window.grab()
    if image.isNull() or not image.save(str(path), "PNG"):
        raise RuntimeError(f"Could not capture Qt workspace: {path}")
    print(f"SCREENSHOT {path}", flush=True)


def _select_tab(widget: object, title: str) -> None:
    tabs = getattr(widget, "_tabs", None)
    if not isinstance(tabs, QTabWidget):
        raise RuntimeError(f"Missing Qt tabs for {title}")
    for index in range(tabs.count()):
        if tabs.tabText(index) == title:
            tabs.setCurrentIndex(index)
            return
    raise RuntimeError(f"Missing expected tab: {title}")


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
            destination = output / f"{filename}.png"
            _capture(window, destination)
            print(f"PASS {route_id}: {len(exports)} export buttons", flush=True)
            extra_views = ()
            if route_id == "macro_intelligence":
                extra_views = (
                    ("Matriz macro", "04-matriz-macro"),
                    ("Curvas TRI", "05-curvas-tri"),
                )
            elif route_id == "price_risk":
                extra_views = (
                    ("Resumen VeR", "06-var-posiciones"),
                    ("Riesgo de Tasa · DV01", "07-dv01-shocks"),
                )
            for tab_name, shot_name in extra_views:
                _select_tab(workspace, tab_name)
                scroll = workspace.findChild(QScrollArea)
                if scroll is not None and route_id == "price_risk":
                    target = (
                        workspace._export_positions_button
                        if tab_name == "Resumen VeR"
                        else workspace._export_shock_button
                    )
                    scroll.ensureWidgetVisible(target)
                app.processEvents()
                _capture(window, output / f"{shot_name}.png")
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
