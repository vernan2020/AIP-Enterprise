from __future__ import annotations

import time

from PySide6.QtWidgets import QWidget

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
        # MainWindow historically opened Ejecutivo synchronously during construction.
        # Keep Inicio immediately available and build heavy workspaces only on demand.
        self._suppress_initial_executive = True
        try:
            super()._build_ui()
        finally:
            self._suppress_initial_executive = False

        self._ribbon.action("Agente IA").triggered.connect(
            lambda _checked=False: self.open_workspace("financial_intelligence")
        )

    def open_workspace(self, route_id: str) -> None:
        if route_id == "executive" and getattr(
            self,
            "_suppress_initial_executive",
            False,
        ):
            return

        started = time.perf_counter()
        try:
            super().open_workspace(route_id)
        finally:
            metrics = getattr(self, "_diagnostic_metrics", None)
            if metrics is not None:
                metrics.workspace_switch_time_ms = (time.perf_counter() - started) * 1000.0

    def _build_workspace_widget(self, route_id: str) -> tuple[QWidget, str]:
        if route_id == "financial_intelligence":
            from aip.ui.modules.intelligence.presenters.financial_intelligence_presenter import (
                FinancialIntelligencePresenter,
            )
            from aip.ui.modules.intelligence.views.financial_intelligence_view import (
                FinancialIntelligenceView,
            )

            return (
                FinancialIntelligenceView(
                    presenter=FinancialIntelligencePresenter(self._demo_factory)
                ),
                "Agente IA",
            )
        return super()._build_workspace_widget(route_id)
