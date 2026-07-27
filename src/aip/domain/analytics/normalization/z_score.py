from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.exceptions import NormalizationError
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics


class ZScoreNormalizer:
    """Normalize values to z-scores using the sample standard deviation by default."""

    def __init__(self, use_sample_std: bool = True) -> None:
        self.use_sample_std = use_sample_std

    def normalize(self, values: list[Decimal]) -> list[Decimal]:
        if not values:
            raise NormalizationError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise NormalizationError("Values must be finite")
        if len(values) == 1:
            return [Decimal("0")]
        stats = DescriptiveStatistics(values, sample=True)
        mean = stats.mean()
        std_dev = stats.standard_deviation()
        if std_dev == 0:
            raise NormalizationError("Cannot compute z-scores for a constant series")
        return [(value - mean) / std_dev for value in values]
