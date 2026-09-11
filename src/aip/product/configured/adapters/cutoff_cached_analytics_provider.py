from __future__ import annotations

from datetime import date
from threading import RLock
from typing import Any

from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.protocols import (
    LiquidityDataProvider,
    MarketDataProvider,
    PortfolioDataProvider,
)


class _CutoffPortfolioPayloadCache:
    """Small thread-safe cache keyed by active cutoff and portfolio snapshot identity."""

    def __init__(
        self,
        portfolio_provider: PortfolioDataProvider,
        valuation_date_context: ValuationDateContext,
        *,
        max_entries: int = 6,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._portfolio_provider = portfolio_provider
        self._valuation_date_context = valuation_date_context
        self._max_entries = max_entries
        self._cache: dict[tuple[date, int], dict[str, Any]] = {}
        self._lock = RLock()

    def key(self) -> tuple[date, int]:
        portfolio = self._portfolio_provider.get_portfolio()
        return (self._valuation_date_context.value, id(portfolio))

    def get(self, key: tuple[date, int]) -> dict[str, Any] | None:
        with self._lock:
            return self._cache.get(key)

    def put(self, key: tuple[date, int], payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._cache[key] = payload
            while len(self._cache) > self._max_entries:
                oldest = next(iter(self._cache))
                self._cache.pop(oldest, None)
        return payload

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class CutoffCachedMarketProvider:
    """Caches expensive market analytics for the active portfolio snapshot."""

    def __init__(
        self,
        delegate: MarketDataProvider,
        portfolio_provider: PortfolioDataProvider,
        valuation_date_context: ValuationDateContext,
    ) -> None:
        self._delegate = delegate
        self._cache = _CutoffPortfolioPayloadCache(
            portfolio_provider,
            valuation_date_context,
        )

    def get_market(self) -> dict[str, Any]:
        key = self._cache.key()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        return self._cache.put(key, self._delegate.get_market())

    def clear_cache(self) -> None:
        self._cache.clear()


class CutoffCachedLiquidityProvider:
    """Caches ICL/portfolio liquidity analytics for the active portfolio snapshot."""

    def __init__(
        self,
        delegate: LiquidityDataProvider,
        portfolio_provider: PortfolioDataProvider,
        valuation_date_context: ValuationDateContext,
    ) -> None:
        self._delegate = delegate
        self._cache = _CutoffPortfolioPayloadCache(
            portfolio_provider,
            valuation_date_context,
        )

    def get_liquidity(self) -> dict[str, Any]:
        key = self._cache.key()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        return self._cache.put(key, self._delegate.get_liquidity())

    def clear_cache(self) -> None:
        self._cache.clear()
