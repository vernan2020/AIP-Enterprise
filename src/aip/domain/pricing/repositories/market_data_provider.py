from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MarketDataProvider:
    """Simple market data provider abstraction for pricing."""

    def get_yield_curve(self, currency: str) -> object | None:
        return None

    def get_spot_rate(self, currency: str, tenor: Decimal) -> Decimal:
        return Decimal("0")
