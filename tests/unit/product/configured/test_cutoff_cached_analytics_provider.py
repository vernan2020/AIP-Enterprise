from __future__ import annotations

from datetime import date
from typing import Any

from aip.product.configured.adapters.cutoff_cached_analytics_provider import (
    CutoffCachedLiquidityProvider,
    CutoffCachedMarketProvider,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext


class _PortfolioProvider:
    def __init__(self) -> None:
        self.payload: dict[str, Any] = {"positions": []}

    def get_portfolio(self) -> dict[str, Any]:
        return self.payload


class _MarketDelegate:
    def __init__(self) -> None:
        self.calls = 0

    def get_market(self) -> dict[str, Any]:
        self.calls += 1
        return {"calls": self.calls}


class _LiquidityDelegate:
    def __init__(self) -> None:
        self.calls = 0

    def get_liquidity(self) -> dict[str, Any]:
        self.calls += 1
        return {"calls": self.calls}


def test_market_cache_reuses_same_cutoff_and_portfolio_snapshot() -> None:
    portfolio = _PortfolioProvider()
    context = ValuationDateContext(date(2026, 8, 31))
    delegate = _MarketDelegate()
    provider = CutoffCachedMarketProvider(delegate, portfolio, context)

    first = provider.get_market()
    second = provider.get_market()

    assert first is second
    assert delegate.calls == 1


def test_market_cache_invalidates_when_portfolio_snapshot_changes() -> None:
    portfolio = _PortfolioProvider()
    context = ValuationDateContext(date(2026, 8, 31))
    delegate = _MarketDelegate()
    provider = CutoffCachedMarketProvider(delegate, portfolio, context)

    provider.get_market()
    portfolio.payload = {"positions": [{"series": "NEW"}]}
    refreshed = provider.get_market()

    assert refreshed["calls"] == 2
    assert delegate.calls == 2


def test_liquidity_cache_invalidates_when_cutoff_changes() -> None:
    portfolio = _PortfolioProvider()
    context = ValuationDateContext(date(2026, 8, 31))
    delegate = _LiquidityDelegate()
    provider = CutoffCachedLiquidityProvider(delegate, portfolio, context)

    provider.get_liquidity()
    context.set(date(2026, 7, 31))
    refreshed = provider.get_liquidity()

    assert refreshed["calls"] == 2
    assert delegate.calls == 2


def test_explicit_cache_clear_forces_recalculation() -> None:
    portfolio = _PortfolioProvider()
    context = ValuationDateContext(date(2026, 8, 31))
    delegate = _LiquidityDelegate()
    provider = CutoffCachedLiquidityProvider(delegate, portfolio, context)

    provider.get_liquidity()
    provider.clear_cache()
    provider.get_liquidity()

    assert delegate.calls == 2
