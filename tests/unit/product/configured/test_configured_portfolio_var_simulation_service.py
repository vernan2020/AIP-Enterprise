from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from aip.domain.portfolio.risk.portfolio_historical_var_service import (
    PortfolioHistoricalVaRResult,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRResult,
)
from aip.product.configured.services.configured_portfolio_var_simulation_service import (
    ConfiguredPortfolioVaRSimulationService,
    PortfolioSimulationAction,
    PortfolioSimulationTrade,
)


class _PortfolioProvider:
    def __init__(self, portfolio: dict[str, Any]) -> None:
        self._portfolio = portfolio

    def get_portfolio(self) -> dict[str, Any]:
        return self._portfolio


class _SimulationVaRService:
    """Capture hypothetical portfolios while returning deterministic fake VeR."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def calculate(
        self,
        *,
        valuation_date: date | None = None,
        portfolio: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> ConfiguredPortfolioVaRResult:
        assert valuation_date == date(2026, 8, 31)
        assert portfolio is not None
        assert force_refresh is True
        snapshot = deepcopy(portfolio)
        self.calls.append(snapshot)
        positions = [item for item in snapshot.get("positions", ()) if isinstance(item, dict)]
        market_value = sum(
            (Decimal(str(item.get("market_value_crc") or 0)) for item in positions),
            Decimal("0"),
        )
        var_crc = market_value * Decimal("0.01")
        portfolio_var = PortfolioHistoricalVaRResult(
            portfolio_market_value_crc=market_value,
            portfolio_var_crc=var_crc,
            portfolio_var_percent=Decimal("1.00"),
            scenario_count=500,
            horizon_observations=21,
            confidence_level=Decimal("0.95"),
            percentile=Decimal("0.05"),
            var_rank=25,
            var_scenario_number=25,
            var_scenario_lagged_date=date(2026, 7, 10),
            var_scenario_date=date(2026, 8, 8),
            selected_scenario_pnl_crc=-var_crc,
            scenario_pnl_crc=(),
            positions=(),
        )
        return ConfiguredPortfolioVaRResult(
            valuation_date=date(2026, 8, 31),
            source_position_count=len(positions),
            eligible_position_count=len(positions),
            policy_excluded_position_count=0,
            grouped_title_count=len(positions),
            calculated_title_count=len(positions),
            excluded_title_count=0,
            source_market_value_crc=market_value,
            eligible_market_value_crc=market_value,
            policy_excluded_market_value_crc=Decimal("0"),
            calculated_market_value_crc=market_value,
            excluded_market_value_crc=Decimal("0"),
            coverage_percent=Decimal("100"),
            vector_dates_available=521,
            window_start_date=date(2024, 8, 30),
            window_end_date=date(2026, 8, 31),
            required_prices=521,
            scenario_count=500,
            horizon_observations=21,
            portfolio_var=portfolio_var,
            excluded_titles=(),
            policy_exclusions=(),
            status="CALCULATED",
        )


def _portfolio() -> dict[str, Any]:
    return {
        "valuation_date": date(2026, 8, 31),
        "positions": [
            {
                "isin": "CR000AAA",
                "series": "G260831",
                "issuer": "GOBIERNO",
                "currency": "CRC",
                "product_code": "TP",
                "maturity_date": date(2028, 8, 31),
                "market_value_crc": 100_000_000.0,
                "market_value": 100_000_000.0,
            },
            {
                "isin": "CR000BBB",
                "series": "BCCR2701",
                "issuer": "BCCR",
                "currency": "CRC",
                "product_code": "BP",
                "maturity_date": date(2027, 1, 15),
                "market_value_crc": 50_000_000.0,
                "market_value": 50_000_000.0,
            },
        ],
        "price_vector": {
            "records": [
                {
                    "isin_if_present": "CR000CCC",
                    "series_or_security_code": "G300101",
                    "issuer": "GOBIERNO",
                    "instrument_type_or_mnemonic": "TP",
                    "maturity_date_if_present": date(2030, 1, 1),
                    "market_price": 98.75,
                    "market_yield": 5.75,
                }
            ]
        },
    }


def test_mixed_buy_and_sell_recalculates_isolated_simulated_portfolio() -> None:
    portfolio = _portfolio()
    original = deepcopy(portfolio)
    calculator = _SimulationVaRService()
    service = ConfiguredPortfolioVaRSimulationService(
        _PortfolioProvider(portfolio),  # type: ignore[arg-type]
        calculator,  # type: ignore[arg-type]
    )
    universe = {item.series: item for item in service.list_securities()}

    result = service.simulate(
        (
            PortfolioSimulationTrade(
                PortfolioSimulationAction.SELL,
                universe["G260831"].security_key,
                Decimal("40000000"),
            ),
            PortfolioSimulationTrade(
                PortfolioSimulationAction.BUY,
                universe["G300101"].security_key,
                Decimal("70000000"),
            ),
        )
    )

    assert portfolio == original
    assert len(calculator.calls) == 2
    assert result.base_market_value_crc == Decimal("150000000.0")
    assert result.simulated_market_value_crc == Decimal("180000000.0")
    assert result.delta_market_value_crc == Decimal("30000000.0")
    assert result.base_var_crc == Decimal("1500000.000")
    assert result.simulated_var_crc == Decimal("1800000.000")
    assert result.delta_var_crc == Decimal("300000.000")
    assert result.relative_var_change_percent == Decimal("20.0")
    assert len(result.trades) == 2
    assert any("PiPCA" in item for item in result.notes)

    simulated_positions = calculator.calls[1]["positions"]
    by_series = {item["series"]: item for item in simulated_positions}
    assert Decimal(str(by_series["G260831"]["market_value_crc"])) == Decimal("60000000.0")
    assert Decimal(str(by_series["G300101"]["market_value_crc"])) == Decimal("70000000.0")


def test_full_sale_removes_position_instead_of_falling_back_to_stale_market_value() -> None:
    portfolio = _portfolio()
    calculator = _SimulationVaRService()
    service = ConfiguredPortfolioVaRSimulationService(
        _PortfolioProvider(portfolio),  # type: ignore[arg-type]
        calculator,  # type: ignore[arg-type]
    )
    held = next(item for item in service.list_securities() if item.series == "G260831")

    result = service.simulate(
        (
            PortfolioSimulationTrade(
                PortfolioSimulationAction.SELL,
                held.security_key,
                Decimal("100000000"),
            ),
        )
    )

    simulated_positions = calculator.calls[1]["positions"]
    assert {item["series"] for item in simulated_positions} == {"BCCR2701"}
    assert result.simulated_market_value_crc == Decimal("50000000.0")


def test_sale_above_current_exposure_is_rejected() -> None:
    portfolio = _portfolio()
    calculator = _SimulationVaRService()
    service = ConfiguredPortfolioVaRSimulationService(
        _PortfolioProvider(portfolio),  # type: ignore[arg-type]
        calculator,  # type: ignore[arg-type]
    )
    held = next(item for item in service.list_securities() if item.series == "BCCR2701")

    with pytest.raises(ValueError, match="exceeds current CRC-equivalent market value"):
        service.simulate(
            (
                PortfolioSimulationTrade(
                    PortfolioSimulationAction.SELL,
                    held.security_key,
                    Decimal("50000001"),
                ),
            )
        )

    assert calculator.calls == []


def test_sell_universe_contains_only_current_holdings_while_buy_includes_pipca() -> None:
    service = ConfiguredPortfolioVaRSimulationService(
        _PortfolioProvider(_portfolio()),  # type: ignore[arg-type]
        _SimulationVaRService(),  # type: ignore[arg-type]
    )

    universe = service.list_securities()

    assert {item.series for item in universe if item.in_portfolio} == {"G260831", "BCCR2701"}
    market_only = [item for item in universe if not item.in_portfolio]
    assert len(market_only) == 1
    assert market_only[0].series == "G300101"
    assert market_only[0].source == "PIPCA"
