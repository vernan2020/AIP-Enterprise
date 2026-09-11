from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.services.configured_portfolio_dv01_service import (
    ConfiguredPortfolioDV01Service,
)


class _PortfolioProvider:
    def get_portfolio(self) -> dict[str, object]:
        return {
            "valuation_date": "2026-08-27",
            "positions": [
                {
                    "isin": "CRTEST000001",
                    "series": "TEST-1",
                    "issuer": "G",
                    "currency": "CRC",
                    "product_code": "tp",
                    "market_value_crc": Decimal("100000000"),
                    "modified_duration": Decimal("2"),
                    "maturity_date": date(2028, 8, 27),
                },
                {
                    "isin": "CRTEST000001",
                    "series": "TEST-1",
                    "issuer": "G",
                    "currency": "CRC",
                    "product_code": "tp",
                    "market_value_crc": Decimal("200000000"),
                    "modified_duration": Decimal("2"),
                    "maturity_date": date(2028, 8, 27),
                },
            ],
        }


def test_dv01_title_detail_uses_same_security_identity_and_aggregates_positions() -> None:
    result = ConfiguredPortfolioDV01Service(_PortfolioProvider()).calculate()

    assert len(result.title_details) == 1
    detail = result.title_details[0]
    assert detail.security_key == "isin:crtest000001"
    assert detail.market_value_crc == Decimal("300000000")
    assert detail.modified_duration == Decimal("2")
    assert detail.dv01_crc == Decimal("60000.0000")
    assert detail.bucket == "1 a 5 años"
    assert detail.position_count == 2
    assert detail.status == "CALCULATED"


def test_dv01_title_detail_reconciles_to_portfolio_total() -> None:
    result = ConfiguredPortfolioDV01Service(_PortfolioProvider()).calculate()

    detail_total = sum(
        (item.dv01_crc or Decimal("0") for item in result.title_details),
        Decimal("0"),
    )
    assert detail_total == result.total_dv01_crc
