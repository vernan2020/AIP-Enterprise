from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class HistoricalPriceObservation:
    """Auditable market-price observation used by historical VeR."""

    valuation_date: date
    market_price: Decimal
    source: str
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.valuation_date, date):
            raise TypeError("valuation_date must be datetime.date")
        if self.market_price <= 0:
            raise ValueError("market_price must be greater than zero")
        if not str(self.source).strip():
            raise ValueError("source is required")


@dataclass(frozen=True, slots=True)
class HistoricalPriceSeries:
    """One security aligned to the common institutional market calendar."""

    security_key: str
    valuation_date: date
    observations: tuple[HistoricalPriceObservation, ...]

    def __post_init__(self) -> None:
        if not self.security_key.strip():
            raise ValueError("security_key is required")
        if not self.observations:
            raise ValueError("historical price series cannot be empty")
        dates = tuple(item.valuation_date for item in self.observations)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise ValueError("historical observations must use unique ascending dates")
        if dates[-1] > self.valuation_date:
            raise ValueError("historical observations cannot exceed valuation_date")

    @property
    def dates(self) -> tuple[date, ...]:
        return tuple(item.valuation_date for item in self.observations)

    @property
    def prices(self) -> tuple[Decimal, ...]:
        return tuple(item.market_price for item in self.observations)

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def synthetic_count(self) -> int:
        return sum(1 for item in self.observations if item.synthetic)

    @property
    def first_date(self) -> date:
        return self.observations[0].valuation_date

    @property
    def last_date(self) -> date:
        return self.observations[-1].valuation_date
