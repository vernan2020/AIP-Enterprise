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
