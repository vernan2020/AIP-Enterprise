from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.financial_math.curves.curve_point import CurvePoint


@dataclass(frozen=True, slots=True)
class MarketCurve:
    """Immutable market curve value object."""

    name: str
    currency: str
    market: str
    source: str
    points: tuple[CurvePoint, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Curve name is required")
        if not self.currency.strip():
            raise ValueError("Currency is required")
        if not self.market.strip():
            raise ValueError("Market is required")
        if not self.source.strip():
            raise ValueError("Source is required")
        if not self.points:
            raise ValueError("At least one curve point is required")

    def zero_rate(self, tenor: Decimal) -> Decimal:
        for point in self.points:
            if point.tenor == tenor:
                return point.zero_rate
        raise KeyError(f"No zero rate for tenor {tenor}")
