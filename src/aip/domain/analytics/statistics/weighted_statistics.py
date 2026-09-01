from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.exceptions import StatisticsError


class WeightedStatistics:
    """Weighted statistics with explicitly normalized weights."""

    def __init__(self, values: list[Decimal], weights: list[Decimal]) -> None:
        if len(values) != len(weights):
            raise StatisticsError("Values and weights must have the same length")
        if not values:
            raise StatisticsError("Values series cannot be empty")
        if any(weight < 0 for weight in weights):
            raise StatisticsError("Weights must be non-negative")
        total_weight = sum(weights, Decimal("0"))
        if total_weight == 0:
            raise StatisticsError("Total weight must be non-zero")
        self.values = values
        self.weights = [weight / total_weight for weight in weights]

    def weighted_mean(self) -> Decimal:
        return sum(
            (value * weight for value, weight in zip(self.values, self.weights)), Decimal("0")
        )

    def weighted_variance(self) -> Decimal:
        mean_value = self.weighted_mean()
        return sum(
            (
                (value - mean_value) ** 2 * weight
                for value, weight in zip(self.values, self.weights)
            ),
            Decimal("0"),
        )

    def weighted_standard_deviation(self) -> Decimal:
        return self.weighted_variance().sqrt()
