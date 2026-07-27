from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.exceptions import InvalidScoreBandError


@dataclass(frozen=True, slots=True)
class ScoreBand:
    """Configurable score band with inclusive/exclusive boundaries."""

    code: str
    label: str
    minimum: Decimal
    maximum: Decimal
    inclusive_minimum: bool = True
    inclusive_maximum: bool = True

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvalidScoreBandError("Code and label are required")
        if self.minimum > self.maximum:
            raise InvalidScoreBandError("Minimum bound cannot exceed maximum bound")

    def contains(self, value: Decimal) -> bool:
        lower_ok = value >= self.minimum if self.inclusive_minimum else value > self.minimum
        upper_ok = value <= self.maximum if self.inclusive_maximum else value < self.maximum
        return lower_ok and upper_ok
