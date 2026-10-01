from __future__ import annotations

from decimal import Decimal

from aip.domain.portfolio.services.portfolio_valuation_comparison_service import (
    PortfolioValuationComparisonInput,
    PortfolioValuationComparisonService,
)


def _input(identity: str, value: str | None) -> PortfolioValuationComparisonInput:
    return PortfolioValuationComparisonInput(
        identity=identity,
        issuer="Emisor",
        currency="CRC",
        valuation_accumulated=Decimal(value) if value is not None else None,
        source_reference=f"master.xlsx · {identity}",
    )


def test_exposes_authoritative_accumulated_valuation_without_recalculation() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "25.5"),))

    row = result.rows[0]
    assert row.valuation_accumulated == Decimal("25.5")
    assert row.status == "Maestro de Inversiones"


def test_preserves_negative_accumulated_valuation() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "-10"),))

    assert result.rows[0].valuation_accumulated == Decimal("-10")


def test_missing_accumulated_valuation_is_not_zero_filled() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", None),))

    assert result.rows[0].valuation_accumulated is None
    assert result.rows[0].status == "Valuacion acumulada ausente o invalida"


def test_aggregates_single_currency_authoritative_values() -> None:
    result = PortfolioValuationComparisonService.calculate(
        (
            _input("A", "25.5"),
            _input("B", "-10"),
            _input("C", "4.5"),
        )
    )

    assert result.gain_total == Decimal("30.0")
    assert result.loss_total == Decimal("10")
    assert result.net_total == Decimal("20.0")
    assert result.gain_count == 2
    assert result.loss_count == 1
    assert result.available_count == 3
    assert result.currency_breakdown[0].label == "CRC"
    assert result.currency_breakdown[0].net == Decimal("20.0")


def test_does_not_aggregate_monetary_totals_across_currencies() -> None:
    crc = _input("CRC", "25.5")
    usd = PortfolioValuationComparisonInput(
        identity="USD",
        issuer="Emisor",
        currency="USD",
        valuation_accumulated=Decimal("10"),
        source_reference="master.xlsx · USD",
    )

    result = PortfolioValuationComparisonService.calculate((crc, usd))

    assert result.gain_total is None
    assert result.loss_total is None
    assert result.net_total is None
    assert {item.label for item in result.currency_breakdown} == {"CRC", "USD"}
