from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Any, Generic, TypeVar

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.protocols import PortfolioDataProvider
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Result,
    ConfiguredPortfolioDV01Service,
)
from aip.product.configured.services.configured_portfolio_rate_shock_service import (
    ConfiguredPortfolioRateShockResult,
    ConfiguredPortfolioRateShockService,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRService,
)
from aip.product.configured.services.configured_portfolio_var_simulation_service import (
    PortfolioSimulationSecurity,
)
from aip.product.configured.services.configured_vector_portfolio_var_simulation_service import (
    ConfiguredVectorPortfolioVaRSimulationService,
)

T = TypeVar("T")


class _PortfolioSnapshotCache(Generic[T]):
    """Thread-safe bounded cache tied to the exact in-memory portfolio snapshot."""

    def __init__(self, *, max_entries: int = 4) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._entries: OrderedDict[int, tuple[dict[str, Any], T]] = OrderedDict()
        self._lock = RLock()

    def get(self, portfolio: dict[str, Any]) -> T | None:
        key = id(portfolio)
        with self._lock:
            cached = self._entries.get(key)
            if cached is None or cached[0] is not portfolio:
                return None
            self._entries.move_to_end(key)
            return cached[1]

    def put(self, portfolio: dict[str, Any], value: T) -> T:
        key = id(portfolio)
        with self._lock:
            self._entries[key] = (portfolio, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class CachedConfiguredPortfolioDV01Service(ConfiguredPortfolioDV01Service):
    """Reuses immutable DV01 results while the portfolio snapshot is unchanged."""

    def __init__(self, portfolio_provider: PortfolioDataProvider) -> None:
        super().__init__(portfolio_provider)
        self._cached_portfolio_provider = portfolio_provider
        self._snapshot_cache: _PortfolioSnapshotCache[ConfiguredPortfolioDV01Result] = (
            _PortfolioSnapshotCache()
        )
        self._calculation_lock = RLock()

    def calculate(
        self, *, portfolio: dict[str, Any] | None = None
    ) -> ConfiguredPortfolioDV01Result:
        source = (
            portfolio if portfolio is not None else self._cached_portfolio_provider.get_portfolio()
        )
        cached = self._snapshot_cache.get(source)
        if cached is not None:
            return cached
        with self._calculation_lock:
            cached = self._snapshot_cache.get(source)
            if cached is not None:
                return cached
            return self._snapshot_cache.put(source, super().calculate(portfolio=source))

    def clear_cache(self) -> None:
        self._snapshot_cache.clear()


class CachedConfiguredPortfolioRateShockService(ConfiguredPortfolioRateShockService):
    """Reuses immutable rate-shock results while the portfolio snapshot is unchanged."""

    def __init__(self, portfolio_provider: PortfolioDataProvider) -> None:
        super().__init__(portfolio_provider)
        self._cached_portfolio_provider = portfolio_provider
        self._snapshot_cache: _PortfolioSnapshotCache[ConfiguredPortfolioRateShockResult] = (
            _PortfolioSnapshotCache()
        )
        self._calculation_lock = RLock()

    def calculate(
        self, *, portfolio: dict[str, Any] | None = None
    ) -> ConfiguredPortfolioRateShockResult:
        source = (
            portfolio if portfolio is not None else self._cached_portfolio_provider.get_portfolio()
        )
        cached = self._snapshot_cache.get(source)
        if cached is not None:
            return cached
        with self._calculation_lock:
            cached = self._snapshot_cache.get(source)
            if cached is not None:
                return cached
            return self._snapshot_cache.put(source, super().calculate(portfolio=source))

    def clear_cache(self) -> None:
        self._snapshot_cache.clear()


class CachedConfiguredVectorPortfolioVaRSimulationService(
    ConfiguredVectorPortfolioVaRSimulationService
):
    """Caches the PiPCA-complete simulator catalog per portfolio/vector snapshot."""

    def __init__(
        self,
        portfolio_provider: ConfiguredPortfolioProvider,
        simulation_var_service: ConfiguredPortfolioVaRService,
    ) -> None:
        super().__init__(portfolio_provider, simulation_var_service)
        self._cached_portfolio_provider = portfolio_provider
        self._snapshot_cache: _PortfolioSnapshotCache[tuple[PortfolioSimulationSecurity, ...]] = (
            _PortfolioSnapshotCache()
        )
        self._calculation_lock = RLock()

    def list_securities(
        self,
        *,
        portfolio: dict[str, Any] | None = None,
    ) -> tuple[PortfolioSimulationSecurity, ...]:
        source = (
            portfolio if portfolio is not None else self._cached_portfolio_provider.get_portfolio()
        )
        cached = self._snapshot_cache.get(source)
        if cached is not None:
            return cached
        with self._calculation_lock:
            cached = self._snapshot_cache.get(source)
            if cached is not None:
                return cached
            return self._snapshot_cache.put(
                source,
                super().list_securities(portfolio=source),
            )

    def clear_cache(self) -> None:
        self._snapshot_cache.clear()
