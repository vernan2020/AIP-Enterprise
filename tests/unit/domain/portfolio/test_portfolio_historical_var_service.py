from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

from aip.domain.portfolio.risk.historical_price_series import (
    HistoricalPriceObservation,
    HistoricalPriceSeries,
)
from aip.domain.portfolio.risk.portfolio_historical_var_service import (
    PortfolioHistoricalVaRService,
    PortfolioVaRPosition,
)


def test_var_applies_accumulated_log_return_directly_to_market_value() -> None:
    valuation_date = date(2026, 8, 28)
    first_date = valuation_date - timedelta(days=520)
    prices = tuple(
        Decimal(str(100 * math.pow(0.99, index)))
        for index in range(PortfolioHistoricalVaRService.REQUIRED_PRICES)
    )
    series = HistoricalPriceSeries(
        security_key="REFERENCE",
        valuation_date=valuation_date,
        observations=tuple(
            HistoricalPriceObservation(
                valuation_date=first_date + timedelta(days=index),
                market_price=price,
                source="REGRESSION",
            )
            for index, price in enumerate(prices)
        ),
    )
    market_value = Decimal("1000000")

    result = PortfolioHistoricalVaRService.calculate(
        positions=(
            PortfolioVaRPosition(
                security_key="REFERENCE",
                series="REFERENCE",
                issuer="REFERENCE",
                currency="CRC",
                market_value_crc=market_value,
                price_series=series,
            ),
        )
    )

    expected_log_return = Decimal(str(21 * math.log(0.99)))
    expected_var = -(market_value * expected_log_return)
    simple_return_var = market_value * (Decimal("1") - Decimal("0.99") ** 21)

    assert abs(result.portfolio_var_crc - expected_var) < Decimal("0.000001")
    assert result.portfolio_var_crc > simple_return_var
    assert result.var_rank == 25
    assert result.scenario_count == 500
    assert result.positions[0].var_without_position_crc == Decimal("0")
    assert result.positions[0].incremental_var_crc == result.portfolio_var_crc


def test_incremental_var_recomputes_portfolio_after_removing_each_position() -> None:
    valuation_date = date(2026, 8, 28)
    first_date = valuation_date - timedelta(days=520)

    def make_position(key: str, daily_factor: float, exposure: str) -> PortfolioVaRPosition:
        prices = tuple(
            Decimal(str(100 * math.pow(daily_factor, index)))
            for index in range(PortfolioHistoricalVaRService.REQUIRED_PRICES)
        )
        series = HistoricalPriceSeries(
            security_key=key,
            valuation_date=valuation_date,
            observations=tuple(
                HistoricalPriceObservation(
                    valuation_date=first_date + timedelta(days=index),
                    market_price=price,
                    source="REGRESSION",
                )
                for index, price in enumerate(prices)
            ),
        )
        return PortfolioVaRPosition(
            security_key=key,
            series=key,
            issuer="REFERENCE",
            currency="CRC",
            market_value_crc=Decimal(exposure),
            price_series=series,
        )

    risky = make_position("RISKY", 0.998, "1000000")
    diversifying = make_position("DIVERSIFYING", 1.001, "500000")
    combined = PortfolioHistoricalVaRService.calculate(positions=(risky, diversifying))
    without_risky = PortfolioHistoricalVaRService.calculate(positions=(diversifying,))
    without_diversifying = PortfolioHistoricalVaRService.calculate(positions=(risky,))
    results = {item.security_key: item for item in combined.positions}

    assert combined.portfolio_var_crc > Decimal("0")
    assert without_risky.portfolio_var_crc == Decimal("0")
    assert (
        results["RISKY"].var_without_position_crc
        == without_risky.portfolio_var_crc
    )
    assert (
        results["DIVERSIFYING"].var_without_position_crc
        == without_diversifying.portfolio_var_crc
    )
    assert results["RISKY"].incremental_var_crc == (
        combined.portfolio_var_crc - without_risky.portfolio_var_crc
    )
    assert results["DIVERSIFYING"].incremental_var_crc == (
        combined.portfolio_var_crc - without_diversifying.portfolio_var_crc
    )
    assert results["RISKY"].incremental_var_crc > 0
    assert results["DIVERSIFYING"].incremental_var_crc < 0
    assert sum(
        (item.pnl_at_portfolio_var_scenario_crc for item in combined.positions),
        Decimal("0"),
    ) == combined.selected_scenario_pnl_crc


def test_incremental_var_reranks_all_scenarios_after_exclusion() -> None:
    valuation_date = date(2026, 8, 28)
    first_date = valuation_date - timedelta(days=520)

    def make_position(key: str, exposure: str, price_formula) -> PortfolioVaRPosition:
        observations = tuple(
            HistoricalPriceObservation(
                valuation_date=first_date + timedelta(days=index),
                market_price=Decimal(str(100 * math.exp(price_formula(index)))),
                source="REGRESSION",
            )
            for index in range(PortfolioHistoricalVaRService.REQUIRED_PRICES)
        )
        return PortfolioVaRPosition(
            security_key=key,
            series=key,
            issuer="REFERENCE",
            currency="CRC",
            market_value_crc=Decimal(exposure),
            price_series=HistoricalPriceSeries(key, valuation_date, observations),
        )

    first = make_position(
        "FIRST", "2000000",
        lambda i: 0.0001 * i + 0.04 * math.sin(0.043 * i) + 0.015 * math.sin(0.13 * i),
    )
    second = make_position(
        "SECOND", "1000000",
        lambda i: -0.00012 * i + 0.025 * math.cos(0.039 * i) + 0.012 * math.sin(0.091 * i),
    )
    full = PortfolioHistoricalVaRService.calculate(positions=(first, second))
    without_first = PortfolioHistoricalVaRService.calculate(positions=(second,))
    without_second = PortfolioHistoricalVaRService.calculate(positions=(first,))

    assert full.var_scenario_number != without_first.var_scenario_number
    assert full.var_scenario_number != without_second.var_scenario_number
    by_key = {item.security_key: item for item in full.positions}
    assert by_key["FIRST"].var_without_position_crc == without_first.portfolio_var_crc
    assert by_key["SECOND"].var_without_position_crc == without_second.portfolio_var_crc
    assert by_key["FIRST"].incremental_var_crc == (
        full.portfolio_var_crc - without_first.portfolio_var_crc
    )
    assert by_key["SECOND"].incremental_var_crc == (
        full.portfolio_var_crc - without_second.portfolio_var_crc
    )
