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
    assert row.status == "Maestro de Inversiones · CRC"


def test_preserves_negative_accumulated_valuation() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", "-10"),))

    assert result.rows[0].valuation_accumulated == Decimal("-10")


def test_missing_accumulated_valuation_is_not_zero_filled() -> None:
    result = PortfolioValuationComparisonService.calculate((_input("A", None),))

    assert result.rows[0].valuation_accumulated is None
    assert result.rows[0].status == "Valuacion acumulada ausente o invalida"


def test_usd_accumulated_valuation_is_preserved_and_converted_to_crc() -> None:
    item = PortfolioValuationComparisonInput(
        identity="USD1",
        issuer="Emisor USD",
        currency="USD",
        valuation_accumulated=Decimal("12.50"),
        source_reference="master.xlsx · USD1",
    )

    result = PortfolioValuationComparisonService.calculate(
        (item,),
        fx_sell_rate=Decimal("503.25"),
        fx_rate_date="2026-09-30",
    )

    row = result.rows[0]
    assert row.valuation_accumulated == Decimal("12.50")
    assert row.valuation_accumulated_crc == Decimal("6290.6250")
    assert row.fx_sell_rate == Decimal("503.25")
    assert row.fx_rate_date == "2026-09-30"
    assert result.gain_total == Decimal("6290.6250")


def test_usd_without_exact_bccr_sell_rate_is_nd_for_consolidation() -> None:
    item = PortfolioValuationComparisonInput(
        identity="USD1",
        issuer="Emisor USD",
        currency="USD",
        valuation_accumulated=Decimal("12.50"),
        source_reference="master.xlsx · USD1",
    )

    result = PortfolioValuationComparisonService.calculate(
        (item,),
        fx_rate_date="2026-09-30",
    )

    row = result.rows[0]
    assert row.valuation_accumulated == Decimal("12.50")
    assert row.valuation_accumulated_crc is None
    assert result.gain_total == Decimal("0")
    assert result.gain_count == 0
    assert "TC venta BCCR" in row.status
