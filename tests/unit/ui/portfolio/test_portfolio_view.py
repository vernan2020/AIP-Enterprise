from __future__ import annotations

from aip.ui.modules.portfolio.views.portfolio_view import PortfolioView


def test_portfolio_view_constructs(qt_app) -> None:
    view = PortfolioView()
    assert view is not None
    assert view.selected_row() is not None


def test_portfolio_view_refresh_and_bind(qt_app) -> None:
    view = PortfolioView()
    view.refresh()
    assert view.view_model().status == "loaded"
