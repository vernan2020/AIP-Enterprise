from __future__ import annotations

from PySide6.QtWidgets import QApplication

from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.shell.intelligence_main_window import FinancialIntelligenceMainWindow


def test_financial_intelligence_shell_keeps_executive_lazy_at_startup() -> None:
    app = QApplication.instance() or QApplication([])
    factory = DemoApplicationFactory(
        DemoConfig(
            execution_mode="DEMO",
            demo_mode_enabled=True,
        )
    )

    window = FinancialIntelligenceMainWindow(demo_factory=factory)
    titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]

    assert "Inicio" in titles
    assert "Ejecutivo" not in titles

    window.open_workspace("executive")
    titles = [window.workspace.tabText(index) for index in range(window.workspace.count())]

    assert "Ejecutivo" in titles
    window.close()
    app.processEvents()
