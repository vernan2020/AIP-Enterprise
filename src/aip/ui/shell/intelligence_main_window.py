from __future__ import annotations

from PySide6.QtWidgets import QWidget

from aip.ui.modules.intelligence.presenters.financial_intelligence_presenter import (
    FinancialIntelligencePresenter,
)
from aip.ui.modules.intelligence.views.financial_intelligence_view import (
    FinancialIntelligenceView,
)
from aip.ui.navigation.routes import Route
from aip.ui.shell.main_window import MainWindow


class FinancialIntelligenceMainWindow(MainWindow):
    """Production shell extension that adds the AIP Financial Copilot workspace."""

    _WORKSPACE_TITLES = {
        **MainWindow._WORKSPACE_TITLES,
        "financial_intelligence": "Agente IA",
    }

    def _setup_navigation(self) -> None:
        super()._setup_navigation()
        self._navigation.register(
            Route(
                "financial_intelligence",
                "Agente IA",
                "intelligence",
            )
        )

    def _build_ui(self) -> None:
        super()._build_ui()
        self._ribbon.action("Agente IA").triggered.connect(
            lambda _checked=False: self.open_workspace("financial_intelligence")
        )

    def _build_workspace_widget(self, route_id: str) -> tuple[QWidget, str]:
        if route_id == "financial_intelligence":
            return (
                FinancialIntelligenceView(
                    presenter=FinancialIntelligencePresenter(self._demo_factory)
                ),
                "Agente IA",
            )
        return super()._build_workspace_widget(route_id)
