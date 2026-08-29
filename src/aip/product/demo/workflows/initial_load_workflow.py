from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aip.product.configured.protocols import (
    LiquidityDataProvider,
    MarketDataProvider,
    PortfolioDataProvider,
    SourceHealthProvider,
)
from aip.product.demo.adapters.demo_health_provider import DemoHealthProvider
from aip.product.demo.adapters.demo_liquidity_provider import DemoLiquidityProvider
from aip.product.demo.adapters.demo_market_provider import DemoMarketProvider
from aip.product.demo.adapters.demo_portfolio_provider import DemoPortfolioProvider
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.product.demo.status.source_status import SourceStatus


class InitialLoadWorkflow:
    """Coordinates the initial demo data load workflow."""

    def __init__(
        self,
        config: DemoConfig,
        portfolio_provider: PortfolioDataProvider | None = None,
        market_provider: MarketDataProvider | None = None,
        liquidity_provider: LiquidityDataProvider | None = None,
        health_provider: SourceHealthProvider | None = None,
    ) -> None:
        self._config = config
        self._portfolio_provider = portfolio_provider or DemoPortfolioProvider()
        self._market_provider = market_provider or DemoMarketProvider()
        self._liquidity_provider = liquidity_provider or DemoLiquidityProvider()
        self._health_provider = health_provider or DemoHealthProvider()

    def execute(self, correlation_id: str) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        health = self._health_provider.get_health()
        source_statuses = tuple(
            SourceStatus(name=name, state=state, correlation_id=correlation_id)
            for name, state in health.items()
        )
        portfolio = self._portfolio_provider.get_portfolio()
        print(
            f"[portfolio-runtime] application-service portfolio_type={type(portfolio).__name__} "
            f"positions={len(portfolio.get('positions', []))} valuation_date={portfolio.get('valuation_date')} "
            f"first_position={portfolio.get('positions', [{}])[0] if portfolio.get('positions') else None}"
        )
        return {
            "execution_id": f"init-{correlation_id}",
            "correlation_id": correlation_id,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "source_statuses": [
                {
                    "name": status.name,
                    "state": status.state,
                    "details": status.details,
                    "correlation_id": status.correlation_id,
                }
                for status in source_statuses
            ],
            "data_quality_status": "HEALTHY",
            "workflow_statuses": {
                "portfolio": "COMPLETED",
                "market": "COMPLETED",
                "liquidity": "COMPLETED",
            },
            "warnings": (),
            "errors": (),
            "calculation_references": {
                "portfolio": "calc-portfolio-demo",
                "market": "calc-market-demo",
                "liquidity": "calc-liquidity-demo",
            },
            "application_readiness": "READY",
            "portfolio": portfolio,
            "market": self._market_provider.get_market(),
            "liquidity": self._liquidity_provider.get_liquidity(),
        }
