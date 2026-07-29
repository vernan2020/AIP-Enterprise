from __future__ import annotations

from aip.ui.modules.market.widgets.market_metric_card import MarketMetricCard
from aip.ui.modules.market.widgets.market_status_badge import MarketStatusBadge
from aip.ui.modules.market.widgets.market_filter_panel import MarketFilterPanel


def test_market_widgets_render(qt_app) -> None:
    card = MarketMetricCard("Market Date", "2026-07-29")
    badge = MarketStatusBadge("Ready")
    filter_panel = MarketFilterPanel()

    assert card is not None
    assert badge.text() == "Ready"
    assert filter_panel is not None
