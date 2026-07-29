from __future__ import annotations

from aip.ui.modules.portfolio.widgets.portfolio_filter_panel import PortfolioFilterPanel
from aip.ui.modules.portfolio.widgets.portfolio_status_badge import PortfolioStatusBadge
from aip.ui.modules.portfolio.widgets.portfolio_table import PortfolioTable


def test_portfolio_widgets_construct(qt_app) -> None:
    filter_panel = PortfolioFilterPanel()
    assert filter_panel.issuer.count() == 2

    badge = PortfolioStatusBadge("Ready")
    assert badge.text() == "Ready"

    table = PortfolioTable()
    assert table.columnCount() == 13
