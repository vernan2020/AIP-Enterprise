from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QTabWidget

from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView


@pytest.fixture
def portfolio_view(qt_app) -> Iterator[PortfolioView]:
    """Close embedded Qt widgets and stop workers before fixture teardown."""
    view = PortfolioView()
    try:
        yield view
    finally:
        view.close()
        view.deleteLater()
        qt_app.processEvents()


def test_portfolio_view_constructs(portfolio_view: PortfolioView) -> None:
    view = portfolio_view
    assert view is not None
    assert view.selected_row() is not None


def test_portfolio_view_exposes_historical_kpi_tab_between_panel_and_positions(
    portfolio_view: PortfolioView,
) -> None:
    view = portfolio_view
    tabs = view.findChild(QTabWidget)

    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Resumen ejecutivo",
        "Histórico KPIs",
        "Ganancia / pérdida",
        "Tasa equivalente y capital",
        "Posiciones",
    ]


def test_portfolio_history_worker_starts_only_when_history_tab_is_opened(
    portfolio_view: PortfolioView, qt_app
) -> None:
    view = portfolio_view
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


def test_portfolio_view_refresh_and_bind(portfolio_view: PortfolioView) -> None:
    view = portfolio_view
    view.refresh()
    assert view.view_model().status == "loaded"
