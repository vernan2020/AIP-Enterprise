from __future__ import annotations

from decimal import Decimal

from aip.product.configured.services.configured_portfolio_valuation_comparison_service import (
    ConfiguredPortfolioValuationComparisonService,
)


def test_configured_service_uses_raw_master_values_and_lineage() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "CRTEST",
                "issuer": "Emisor",
                "market_value": 0.0,
                "book_value": 0.0,
                "valuation_comparison_source": {
                    "currency": "CRC",
                    "market_value": 125.5,
                    "book_value": 100,
                    "source_file": "Maestro.xlsx",
                    "source_row": 42,
                },
            }
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(portfolio)

    row = result.rows[0]
    assert row.source.market_value == Decimal("125.5")
    assert row.source.book_value == Decimal("100")
    assert row.difference == Decimal("25.5")
    assert row.source.source_reference == "Maestro.xlsx · fila 42"


def test_configured_service_does_not_reuse_zero_filled_display_values() -> None:
    portfolio = {
        "positions": [
            {
                "isin": "CRTEST",
                "issuer": "Emisor",
                "currency": "CRC",
                "market_value": 0.0,
                "book_value": 0.0,
                "valuation_comparison_source": {
                    "currency": "CRC",
                    "market_value": None,
                    "book_value": None,
                    "source_file": "Maestro.xlsx",
                    "source_row": 7,
                },
            }
        ]
    }

    result = ConfiguredPortfolioValuationComparisonService.calculate(portfolio)

    assert result.rows[0].difference is None
    assert result.rows[0].status == "Valor ausente o inválido"
    assert result.totals[0].included_count == 0
