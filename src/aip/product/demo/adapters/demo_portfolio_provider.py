from __future__ import annotations

from typing import Any

from aip.product.demo.data.demo_portfolio_data import DemoPortfolioData


class DemoPortfolioProvider:
    """Adapts demo portfolio data to application-facing output."""

    def get_portfolio(self) -> dict[str, Any]:
        return DemoPortfolioData.build()
