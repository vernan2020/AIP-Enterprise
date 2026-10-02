from __future__ import annotations

from decimal import Decimal

from aip.product.configured.services.configured_portfolio_valuation_comparison_service import (
    ConfiguredPortfolioValuationComparisonService,
)


def test_configured_service_uses_accumulated_valuation_and_lineage() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "CRTEST",
                "issuer": "Emisor",
                "valuation_accumulated_source": {
                    "currency": "CRC",
                    "value": 25.5,
                    "source_file": "Maestro.xlsx",
                    "source_row": 42,
                },
            }
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(portfolio)

    row = result.rows[0]
    assert row.valuation_accumulated == Decimal("25.5")
    assert row.source.currency == "CRC"
    assert row.source.source_reference == "Maestro.xlsx · fila 42"


def test_configured_service_does_not_derive_from_market_or_book_values() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "CRTEST",
                "issuer": "Emisor",
                "market_value": 999.0,
                "book_value": 1.0,
                "valuation_accumulated_source": {
                    "currency": "CRC",
                    "value": None,
                    "source_file": "Maestro.xlsx",
                    "source_row": 7,
                },
            }
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(portfolio)

    assert result.rows[0].valuation_accumulated is None
    assert result.rows[0].status == "Valuacion acumulada ausente o invalida"


def test_configured_service_aggregates_only_real_accumulated_valuation() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "GAIN1",
                "issuer": "Emisor A",
                "valuation_accumulated_source": {
                    "currency": "CRC",
                    "value": 100,
                    "source_file": "Maestro.xlsx",
                    "source_row": 2,
                },
            },
            {
                "isin": "LOSS1",
                "issuer": "Emisor A",
                "valuation_accumulated_source": {
                    "currency": "CRC",
                    "value": -40,
                    "source_file": "Maestro.xlsx",
                    "source_row": 3,
                },
            },
            {
                "isin": "GAIN2",
                "issuer": "Emisor B",
                "valuation_accumulated_source": {
                    "currency": "USD",
                    "value": 20,
                    "source_file": "Maestro.xlsx",
                    "source_row": 4,
                },
            },
            {
                "isin": "MISSING",
                "issuer": "Emisor C",
                "valuation_accumulated_source": {
                    "currency": "USD",
                    "value": None,
                    "source_file": "Maestro.xlsx",
                    "source_row": 5,
                },
            },
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(
        portfolio,
        fx_sell_rate=Decimal("2"),
        fx_rate_date="2026-09-30",
    )

    assert result.gain_total == Decimal("140")
    assert result.loss_total == Decimal("-40")
    assert result.net_total == Decimal("100")
    assert result.gain_count == 2
    assert result.loss_count == 1
    assert [row.source.identity for row in result.top_gains] == ["GAIN1", "GAIN2"]
    assert [row.source.identity for row in result.top_losses] == ["LOSS1"]
    assert [row.source.identity for row in result.top_positions] == ["GAIN1", "LOSS1", "GAIN2"]

    currencies = {item.label: item for item in result.currency_contributions}
    assert currencies["CRC"].gain == Decimal("100")
    assert currencies["CRC"].loss == Decimal("-40")
    assert currencies["USD"].gain == Decimal("40")
    assert currencies["USD"].loss == Decimal("0")


def test_configured_service_preserves_original_usd_and_uses_crc_reporting_value() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "USD1",
                "issuer": "Emisor USD",
                "valuation_accumulated_source": {
                    "currency": "USD",
                    "value": "10.25",
                    "source_file": "Maestro.xlsx",
                    "source_row": 8,
                },
            }
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(
        portfolio,
        fx_sell_rate=Decimal("500"),
        fx_rate_date="2026-09-30",
    )

    row = result.rows[0]
    assert row.valuation_accumulated == Decimal("10.25")
    assert row.valuation_accumulated_crc == Decimal("5125.00")
    assert row.fx_sell_rate == Decimal("500")
