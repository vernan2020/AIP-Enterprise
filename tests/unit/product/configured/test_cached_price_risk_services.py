from __future__ import annotations

from aip.core.container import Container
from aip.product.configured.bootstrap.configured_dependency_composition import (
    ConfiguredDependencyComposition,
)
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.services.cached_price_risk_services import (
    CachedConfiguredPortfolioDV01Service,
    CachedConfiguredPortfolioRateShockService,
    CachedConfiguredVectorPortfolioVaRSimulationService,
    _PortfolioSnapshotCache,
)
from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)
from aip.product.configured.services.configured_portfolio_rate_shock_service import (
    ConfiguredPortfolioRateShockService,
)
from aip.product.configured.services.configured_portfolio_var_simulation_service import (
    ConfiguredPortfolioVaRSimulationService,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def test_snapshot_cache_reuses_only_exact_portfolio_object() -> None:
    cache: _PortfolioSnapshotCache[str] = _PortfolioSnapshotCache()
    first: dict[str, object] = {"valuation_date": "2026-08-31"}
    equivalent: dict[str, object] = {"valuation_date": "2026-08-31"}

    cache.put(first, "cached")

    assert cache.get(first) == "cached"
    assert cache.get(equivalent) is None


def test_configured_composition_uses_cached_price_risk_services() -> None:
    container = ConfiguredDependencyComposition(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False),
        ConfiguredSourceConfig(),
    ).compose(Container())

    dv01 = container.resolve(ConfiguredPortfolioDV01Service)
    rate_shock = container.resolve(ConfiguredPortfolioRateShockService)
    simulator = container.resolve(ConfiguredPortfolioVaRSimulationService)

    assert isinstance(dv01, CachedConfiguredPortfolioDV01Service)
    assert isinstance(rate_shock, CachedConfiguredPortfolioRateShockService)
    assert isinstance(simulator, CachedConfiguredVectorPortfolioVaRSimulationService)
