from __future__ import annotations

from typing import Any


class DemoMarketData:
    """Deterministic market data for demo mode."""

    @staticmethod
    def build() -> dict[str, Any]:
        return {
            "market_date": "2026-07-29",
            "curves": [
                {"label": "USD 3M", "value": 3.10, "tenor": "3M"},
                {"label": "USD 6M", "value": 3.20, "tenor": "6M"},
                {"label": "USD 1Y", "value": 3.35, "tenor": "1Y"},
            ],
            "pricing_results": [
                {"issuer": "Acme Bank", "instrument": "Treasury Bill", "market_value": 100.00, "benchmark_yield": 3.10},
            ],
            "relative_value_results": [
                {"issuer": "Blue Ridge", "recommendation": "BUY", "confidence": "High", "spread": 0.45},
            ],
            "market_status": "Ready",
            "average_yield": 3.10,
            "average_duration": 4.50,
            "average_spread": 0.45,
            "relative_value_opportunities": 1,
        }
