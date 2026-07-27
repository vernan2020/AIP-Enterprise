from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.exceptions import NormalizationError


class PercentileRank:
    """Compute percentile ranks with explicit tie handling."""

    def __init__(self, tie_method: str = "average") -> None:
        self.tie_method = tie_method

    def normalize(self, values: list[Decimal]) -> list[Decimal]:
        if not values:
            raise NormalizationError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise NormalizationError("Values must be finite")
        if len(values) == 1:
            return [Decimal("1")]
        ordered = sorted(values)
        results: list[Decimal] = []
        for value in values:
            rank_count = sum(1 for item in ordered if item < value)
            tie_count = sum(1 for item in ordered if item == value)
            if tie_count == 1:
                percentile = Decimal(rank_count + 1) / Decimal(len(ordered))
            else:
                if self.tie_method == "average":
                    percentile = Decimal(rank_count + 1) / Decimal(len(ordered))
                else:
                    percentile = Decimal(rank_count + tie_count) / Decimal(len(ordered))
            results.append(percentile)
        return results
