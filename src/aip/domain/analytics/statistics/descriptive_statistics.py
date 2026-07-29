from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from aip.domain.analytics.exceptions import StatisticsError


class DescriptiveStatistics:
    """Decimal-based descriptive statistics with explicit sample/population choices."""

    def __init__(self, values: list[Decimal], sample: bool = False) -> None:
        if not values:
            raise StatisticsError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise StatisticsError("Values must be finite")
        self.values = values
        self.sample = sample

    def count(self) -> int:
        return len(self.values)

    def sum(self) -> Decimal:
        return sum(self.values, Decimal("0"))

    def minimum(self) -> Decimal:
        return min(self.values)

    def maximum(self) -> Decimal:
        return max(self.values)

    def mean(self) -> Decimal:
        return self.sum() / Decimal(len(self.values))

    def median(self) -> Decimal:
        ordered = sorted(self.values)
        length = len(ordered)
        middle = length // 2
        if length % 2 == 0:
            return (ordered[middle - 1] + ordered[middle]) / Decimal("2")
        return ordered[middle]

    def variance(self) -> Decimal:
        mean_value = self.mean()
        squared_diffs = [(value - mean_value) ** 2 for value in self.values]
        divisor = Decimal(len(self.values) - 1) if self.sample else Decimal(len(self.values))
        if divisor == 0:
            return Decimal("0")
        return sum(squared_diffs, Decimal("0")) / divisor

    def standard_deviation(self) -> Decimal:
        return self.variance().sqrt()

    def quartiles(self) -> tuple[Decimal, Decimal, Decimal]:
        ordered = sorted(self.values)
        length = len(ordered)
        if length == 1:
            return ordered[0], ordered[0], ordered[0]
        q1 = self._percentile(ordered, Decimal("0.25"))
        q3 = self._percentile(ordered, Decimal("0.75"))
        return q1, self.median(), q3

    def interquartile_range(self) -> Decimal:
        q1, _, q3 = self.quartiles()
        return q3 - q1

    def percentile(self, percentile: Decimal) -> Decimal:
        if not Decimal("0") <= percentile <= Decimal("1"):
            raise StatisticsError("Percentile must be between 0 and 1")
        return self._percentile(sorted(self.values), percentile)

    def coefficient_of_variation(self) -> Decimal:
        mean_value = self.mean()
        if mean_value == 0:
            raise StatisticsError("Coefficient of variation is undefined for zero mean")
        return self.standard_deviation() / mean_value

    def _percentile(self, ordered: list[Decimal], percentile: Decimal) -> Decimal:
        if len(ordered) == 1:
            return ordered[0]
        rank = (Decimal(len(ordered)) - Decimal("1")) * percentile
        lower_index = int(rank.to_integral_value(rounding=ROUND_FLOOR))
        upper_index = int(rank.to_integral_value(rounding=ROUND_CEILING))
        if lower_index == upper_index:
            return ordered[lower_index]
        fraction = rank - Decimal(lower_index)
        return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction

    def _round(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.0000000001"))
