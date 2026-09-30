from __future__ import annotations

from decimal import Decimal

from aip.domain.portfolio.services.portfolio_valuation_comparison_service import (
    PortfolioValuationComparisonInput,
    PortfolioValuationComparisonService,
)


def _input(
    identity: str,
    currency: str,
    market: str | None,
    book: str | None,
) -> PortfolioValuationComparisonInput:
    return PortfolioValuationComparisonInput(
        identity=identity,
        issuer="Emisor",
        currency=currency,
        market_value=Decimal(market) if market is not None else None,
        book_value=Decimal(book) if book is not None else None,
        source_reference=f"master.xlsx · {identity}",
    )


def test_calculates_unrealized_gain_and_percentage() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "CRC", "110", "100"),))

    row = result.rows[0]
    assert row.difference == Decimal("10")
    assert row.percentage == Decimal("10")
    assert row.status == "Calculado"
    assert result.totals[0].difference == Decimal("10")


def test_calculates_unrealized_loss() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "USD", "90", "100"),))

    assert result.rows[0].difference == Decimal("-10")
    assert result.rows[0].percentage == Decimal("-10")


def test_keeps_currencies_separate() -> None:
    result = PortfolioValuationComparisonService.calculate(
        (
            _input("A", "CRC", "110", "100"),
            _input("B", "USD", "220", "200"),
        )
    )

    assert [(item.currency, item.difference) for item in result.totals] == [
        ("CRC", Decimal("10")),
        ("USD", Decimal("20")),
    ]


def test_missing_values_are_not_zero_filled() -> None:
    result = PortfolioValuationComparisonService.calculate(
        (
            _input("A", "CRC", None, "100"),
            _input("B", "CRC", "120", "100"),
        )
    )

    assert result.rows[0].difference is None
    assert result.rows[0].status == "Valor ausente o inválido"
    total = result.totals[0]
    assert total.market_value == Decimal("120")
    assert total.book_value == Decimal("100")
    assert total.included_count == 1
    assert total.total_count == 2


def test_missing_currency_is_not_included_in_currency_total() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "", "110", "100"),))

    assert result.rows[0].status == "Moneda ausente"
    assert result.totals[0].currency == "N/D"
    assert result.totals[0].included_count == 0
    assert result.totals[0].market_value == Decimal("0")


def test_zero_book_value_keeps_difference_but_percentage_unavailable() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "CRC", "10", "0"),))

    assert result.rows[0].difference == Decimal("10")
    assert result.rows[0].percentage is None
    assert result.totals[0].percentage is None
