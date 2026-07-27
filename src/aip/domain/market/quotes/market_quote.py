from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Immutable quote carrying core market metrics for an instrument."""

    instrument_id: str
    currency: str
    market: str
    source: str
    price: Decimal
    yield_rate: Decimal
    duration: Decimal
    convexity: Decimal
    dv01: Decimal
    pvbp: Decimal
    spread: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "instrument_id": self.instrument_id,
            "currency": self.currency,
            "market": self.market,
            "source": self.source,
            "price": self.price,
            "yield_rate": self.yield_rate,
            "duration": self.duration,
            "convexity": self.convexity,
            "dv01": self.dv01,
            "pvbp": self.pvbp,
            "spread": self.spread,
        }
