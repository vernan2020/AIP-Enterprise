from __future__ import annotations

from dataclasses import dataclass

from aip.domain.market.quotes.market_quote import MarketQuote


@dataclass(frozen=True)
class PriceQuote(MarketQuote):
    """Quote specialized for price-based market observations."""

    def to_dict(self) -> dict[str, object]:
        data = super().to_dict()
        data["price"] = self.price
        return data
