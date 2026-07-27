from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from aip.domain.market.curves.curve_snapshot import CurveSnapshot
from aip.domain.market.exceptions import MarketSnapshotError
from aip.domain.market.quotes.market_quote import MarketQuote
from aip.domain.market.versioning.snapshot_version import SnapshotVersion


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Immutable market snapshot aggregate root."""

    valuation_date: date
    market: str
    source: str
    currency: str
    quotes: tuple[MarketQuote, ...]
    curves: tuple[CurveSnapshot, ...]
    version: SnapshotVersion
    timestamp: datetime

    def __post_init__(self) -> None:
        if not self.market.strip():
            raise MarketSnapshotError("Market is required")
        if not self.source.strip():
            raise MarketSnapshotError("Source is required")
        if not self.currency.strip():
            raise MarketSnapshotError("Currency is required")
        if not self.quotes:
            raise MarketSnapshotError("At least one quote is required")
        if not self.curves:
            raise MarketSnapshotError("At least one curve is required")

    def get_quote(self, instrument_id: str) -> MarketQuote | None:
        for quote in self.quotes:
            if quote.instrument_id == instrument_id:
                return quote
        return None

    @property
    def price(self) -> object:
        if not self.quotes:
            return None
        return self.quotes[0].price

    @property
    def yield_rate(self) -> object:
        if not self.quotes:
            return None
        return self.quotes[0].yield_rate
