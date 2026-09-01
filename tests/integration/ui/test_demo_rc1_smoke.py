from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QLabel

from aip.ui.shell.main_window import MainWindow


def test_demo_rc1_smoke_navigation_and_refresh() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    window = MainWindow()
    window.show()
    app.processEvents()

    assert any("DEMO MODE" in widget.text().upper() for widget in window.findChildren(QLabel))

    workspace = window.workspace
    assert any(workspace.tabText(index) == "Executive" for index in range(workspace.count()))

    window.open_workspace("portfolio")
    window.open_workspace("market")
    window.open_workspace("liquidity")
    window.open_workspace("treasury")
    app.processEvents()

    assert workspace.count() >= 6
    assert workspace.tabText(workspace.currentIndex()) in {
        "Portfolio",
        "Market",
        "Liquidity",
        "Treasury",
    }

    summary = window.refresh_all()
    assert summary["status"] == "completed"
    assert summary["correlation_id"]
    assert window.statusBar().currentMessage() != ""

    window.close()
    app.processEvents()
