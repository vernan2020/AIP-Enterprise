from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BCCRResponse:
    """Simplified response model for a single BCCR indicator value."""

    indicator_code: str
    value: Decimal | float | int
    observation_date: str
    source: str = "bccr"

    def to_dict(self) -> dict[str, object]:
        return {
            "indicator_code": self.indicator_code,
            "value": self.value,
            "observation_date": self.observation_date,
            "source": self.source,
        }
