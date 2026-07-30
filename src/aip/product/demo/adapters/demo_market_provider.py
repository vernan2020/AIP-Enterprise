from __future__ import annotations

from typing import Any

from aip.product.demo.data.demo_market_data import DemoMarketData


class DemoMarketProvider:
    """Adapts demo market data to application-facing output."""

    def get_market(self) -> dict[str, Any]:
        return DemoMarketData.build()
