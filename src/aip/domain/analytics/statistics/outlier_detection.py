from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.enums.outlier_method import OutlierMethod
from aip.domain.analytics.exceptions import StatisticsError
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics


@dataclass(frozen=True, slots=True)
class OutlierResult:
    """Result object describing detected outliers."""

    outliers: tuple[Decimal, ...]
    threshold: Decimal
    method: OutlierMethod
    supporting_statistic: Decimal
    explanation: str


class OutlierDetection:
    """Detect outliers using several documented methods."""

    def __init__(self, method: OutlierMethod) -> None:
        self.method = method

    def detect(self, values: list[Decimal], threshold: Decimal | None = None) -> OutlierResult:
        if not values:
            raise StatisticsError("Values series cannot be empty")
        if any(value.is_nan() or value.is_infinite() for value in values):
            raise StatisticsError("Values must be finite")
        stats = DescriptiveStatistics(values, sample=True)
        if self.method is OutlierMethod.IQR:
            q1, _, q3 = stats.quartiles()
            iqr = q3 - q1
            threshold_value = threshold or Decimal("1.5") * iqr
            lower_bound = q1 - threshold_value
            upper_bound = q3 + threshold_value
            outliers = tuple(value for value in values if value < lower_bound or value > upper_bound)
            return OutlierResult(outliers, threshold_value, self.method, iqr, "Outliers beyond the IQR fence")
        if self.method is OutlierMethod.Z_SCORE:
            mean_value = stats.mean()
            std_dev = stats.standard_deviation()
            if std_dev == 0:
                raise StatisticsError("Z-score outlier detection requires non-zero standard deviation")
            threshold_value = threshold or Decimal("1.3")
            z_scores = [(value - mean_value) / std_dev for value in values]
            outliers = tuple(value for value, score in zip(values, z_scores) if abs(score) >= threshold_value)
            return OutlierResult(outliers, threshold_value, self.method, std_dev, "Outliers beyond the z-score threshold")
        median = stats.median()
        mad = sum(abs(value - median) for value in values) / Decimal(len(values))
        threshold_value = threshold or Decimal("3.5")
        outliers = tuple(value for value in values if abs((value - median) / mad) > threshold_value)
        return OutlierResult(outliers, threshold_value, self.method, mad, "Outliers beyond the modified z-score threshold")
