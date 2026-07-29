from __future__ import annotations

from aip.ui.modules.liquidity.widgets.liquidity_metric_card import LiquidityMetricCard
from aip.ui.modules.liquidity.widgets.liquidity_status_badge import LiquidityStatusBadge


def test_liquidity_widgets_render(qt_app) -> None:
    card = LiquidityMetricCard("Cash Position", "100.00")
    badge = LiquidityStatusBadge("Healthy")

    assert card.text() == "Cash Position"
    assert badge.text() == "Healthy"
