from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.market.quotes.market_quote import MarketQuote


@dataclass(frozen=True, slots=True)
class YieldQuote(MarketQuote):
    """Quote specialized for yield-based market observations."""

    def to_dict(self) -> dict[str, object]:
        data = super().to_dict()
        data["yield_rate"] = self.yield_rate
        return data
