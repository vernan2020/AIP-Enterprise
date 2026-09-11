from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QTabWidget

from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView


def test_portfolio_view_constructs(qt_app) -> None:
    view = PortfolioView()
    assert view is not None
    assert view.selected_row() is not None


def test_portfolio_view_exposes_historical_kpi_tab_between_panel_and_positions(qt_app) -> None:
    view = PortfolioView()
    tabs = view.findChild(QTabWidget)

    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Panel",
        "Histórico KPIs",
        "Posiciones",
    ]


def test_portfolio_history_worker_starts_only_when_history_tab_is_opened(qt_app) -> None:
    view = PortfolioView()
    try:
        tabs = view.findChild(QTabWidget)
        assert tabs is not None
        assert view.findChild(QThread, "portfolioHistoryWorkerThread") is None

        tabs.setCurrentIndex(1)
        qt_app.processEvents()

        thread = view.findChild(QThread, "portfolioHistoryWorkerThread")
        assert thread is not None
        assert thread.isRunning()
    finally:
        view.close()
        qt_app.processEvents()


def test_portfolio_view_refresh_and_bind(qt_app) -> None:
    view = PortfolioView()
    view.refresh()
    assert view.view_model().status == "loaded"
