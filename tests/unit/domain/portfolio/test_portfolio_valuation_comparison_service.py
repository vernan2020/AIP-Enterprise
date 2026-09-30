from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_valuation_comparison_service import (
    PortfolioValuationComparisonService,
    ValuationComparisonInput,
)


def position(market, book, currency="CRC"):
    return ValuationComparisonInput("series", "issuer", currency, market, book, "master · 2")


def test_totals_are_currency_separated_and_percentage_uses_aggregate_book_value():
    result = PortfolioValuationComparisonService.calculate(
        (
            position(Decimal("120"), Decimal("100")),
            position(Decimal("270"), Decimal("300")),
            position(Decimal("95"), Decimal("100"), "USD"),
        )
    )
    crc, usd = result.totals
    assert crc.difference == Decimal("-10")
    assert crc.percentage == Decimal("-2.5")
    assert usd.difference == Decimal("-5")
    assert result.rows[0].percentage == Decimal("20")


@pytest.mark.parametrize("invalid", [None, Decimal("NaN"), Decimal("Infinity"), Decimal("-1")])
def test_invalid_pairs_are_visible_but_excluded_from_both_totals(invalid):
    result = PortfolioValuationComparisonService.calculate(
        (position(invalid, Decimal("100")), position(Decimal("110"), Decimal("100")))
    )
    assert result.rows[0].difference is None
    assert result.totals[0].market_value == Decimal("110")
    assert result.totals[0].book_value == Decimal("100")
    assert result.totals[0].included_count == 1
    assert result.totals[0].total_count == 2


def test_zero_is_observed_value_and_unknown_currency_is_not_inferred():
    result = PortfolioValuationComparisonService.calculate(
        (
            position(Decimal("0"), Decimal("100")),
            position(Decimal("10"), Decimal("0"), "USD"),
            position(Decimal("20"), Decimal("10"), ""),
        )
    )
    assert result.rows[0].percentage == Decimal("-100")
    assert result.rows[1].difference == Decimal("10")
    assert result.rows[1].percentage is None
    assert result.rows[2].difference is None
    assert result.totals[0].difference is None
    assert PortfolioValuationComparisonService.calculate(()).totals == ()
