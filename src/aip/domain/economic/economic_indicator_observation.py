from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EconomicIndicatorObservation:
    """Normalized economic observation independent from its physical source."""

    indicator_code: str
    observation_date: date
    value: Decimal
    source: str
    unit: str
    source_series_code: str | None = None
    quality_status: str = "VALID"
    is_preliminary: bool = False
