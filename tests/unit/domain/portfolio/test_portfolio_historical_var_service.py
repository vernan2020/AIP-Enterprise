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
