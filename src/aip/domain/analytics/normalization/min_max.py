from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.exceptions import NormalizationError


class MinMaxNormalizer:
    """Normalize a series to a configurable target range using Decimal arithmetic."""

    def __init__(self, lower: Decimal = Decimal("0"), upper: Decimal = Decimal("1")) -> None:
        if lower >= upper:
            raise NormalizationError("Lower bound must be smaller than upper bound")
        self.lower = lower
        self.upper = upper

    def normalize(self, values: list[Decimal]) -> list[Decimal]:
        if not values:
            raise NormalizationError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise NormalizationError("Values must be finite")
        minimum = min(values)
        maximum = max(values)
        if minimum == maximum:
            return [self.lower for _ in values]
        span = maximum - minimum
        return [
            ((value - minimum) / span) * (self.upper - self.lower) + self.lower
            for value in values
        ]
