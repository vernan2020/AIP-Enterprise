from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.exceptions import NormalizationError
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics


class RobustScaler:
    """Normalize values using median and interquartile range."""

    def normalize(self, values: list[Decimal]) -> list[Decimal]:
        if not values:
            raise NormalizationError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise NormalizationError("Values must be finite")
        if len(values) == 1:
            return [Decimal("0")]
        stats = DescriptiveStatistics(values, sample=True)
        median = stats.median()
        iqr = stats.interquartile_range()
        if iqr == 0:
            raise NormalizationError("Cannot compute robust scaling for a constant series")
        return [(value - median) / iqr for value in values]
