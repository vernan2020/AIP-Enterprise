from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from aip.domain.analytics.exceptions import AnalyticsError


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """Immutable metric observation with Decimal-safe validation."""

    metric_name: str
    value: Decimal
    unit: str | None = None
    source: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.metric_name.strip():
            raise AnalyticsError("Metric name is required")
        try:
            value = Decimal(self.value)
        except (InvalidOperation, TypeError) as exc:
            raise AnalyticsError("Metric value must be a valid Decimal") from exc
        if not value.is_finite():
            raise AnalyticsError("Metric value must be finite")
        object.__setattr__(self, "value", value)
        if self.metadata is not None:
            object.__setattr__(self, "metadata", deepcopy(self.metadata))
