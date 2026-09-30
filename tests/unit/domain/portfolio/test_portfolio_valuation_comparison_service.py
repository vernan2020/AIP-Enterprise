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
