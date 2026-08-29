from __future__ import annotations

from typing import Any, Protocol


class PortfolioDataProvider(Protocol):
    def get_portfolio(self) -> dict[str, Any]:
        ...


class MarketDataProvider(Protocol):
    def get_market(self) -> dict[str, Any]:
        ...


class LiquidityDataProvider(Protocol):
    def get_liquidity(self) -> dict[str, Any]:
        ...


class EconomicIndicatorsProvider(Protocol):
    def get_indicators(self) -> dict[str, Any]:
        ...


class SourceHealthProvider(Protocol):
    def get_health(self) -> dict[str, Any]:
        ...
