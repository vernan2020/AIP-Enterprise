from __future__ import annotations

from typing import Any


class DemoPortfolioData:
    """Deterministic portfolio data for demo mode."""

    @staticmethod
    def build() -> dict[str, Any]:
        return {
            "portfolio_name": "Coopealianza Demo Portfolio",
            "valuation_date": "2026-07-29",
            "market_value": 1250000.00,
            "book_value": 1220000.00,
            "weighted_yield": 4.20,
            "modified_duration": 3.40,
            "positions": [
                {
                    "isin": "US0000001",
                    "issuer": "Acme Bank",
                    "instrument": "Treasury Bill",
                    "currency": "USD",
                    "nominal": 1000000.0,
                    "market_value": 1000000.0,
                    "book_value": 980000.0,
                    "yield_value": 4.10,
                    "modified_duration": 0.50,
                    "classification": "Govt",
                    "hqla_status": "Eligible",
                    "mil_status": "Eligible",
                    "recommendation": "Hold",
                    "encumbered": False,
                },
                {
                    "isin": "CRC0000002",
                    "issuer": "Blue Ridge",
                    "instrument": "Corporate Bond",
                    "currency": "CRC",
                    "nominal": 250000.0,
                    "market_value": 240000.0,
                    "book_value": 245000.0,
                    "yield_value": 5.60,
                    "modified_duration": 2.10,
                    "classification": "Corporate",
                    "hqla_status": "Ineligible",
                    "mil_status": "Eligible",
                    "recommendation": "Accumulate",
                    "encumbered": True,
                },
            ],
            "hqla_percent": 68.0,
            "mil_eligible_percent": 82.0,
            "currency_distribution": ("USD", "CRC"),
            "relative_value_opportunity": "BUY",
        }
