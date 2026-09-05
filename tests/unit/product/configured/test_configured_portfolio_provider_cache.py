from __future__ import annotations

from datetime import date
from types import MethodType
from typing import Any

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def test_portfolio_provider_reuses_payload_for_active_valuation_date() -> None:
    provider = ConfiguredPortfolioProvider(DemoConfig(data_cutoff_date=date(2026, 8, 28)))
    calls = 0
    expected: dict[str, Any] = {
        "valuation_date": "2026-08-28",
        "positions": [],
    }

    def _load_portfolio(_self: ConfiguredPortfolioProvider) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return expected

    provider._load_portfolio = MethodType(_load_portfolio, provider)  # type: ignore[method-assign]

    assert provider.get_portfolio() is expected
    assert provider.get_portfolio() is expected
    assert calls == 1


def test_portfolio_provider_explicit_cache_clear_forces_source_reload() -> None:
    provider = ConfiguredPortfolioProvider(DemoConfig(data_cutoff_date=date(2026, 8, 28)))
    calls = 0

    def _load_portfolio(_self: ConfiguredPortfolioProvider) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"valuation_date": "2026-08-28", "load": calls}

    provider._load_portfolio = MethodType(_load_portfolio, provider)  # type: ignore[method-assign]

    first = provider.get_portfolio()
    provider.clear_cache()
    second = provider.get_portfolio()

    assert first["load"] == 1
    assert second["load"] == 2
    assert calls == 2
