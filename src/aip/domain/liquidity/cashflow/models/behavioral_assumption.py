from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BehavioralAssumption:
    """Configurable behavioral assumption for cash flow projections."""

    name: str
    probability: Decimal
    effect_ratio: Decimal
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Behavioral assumption name is required")
        if self.probability < 0 or self.probability > 1:
            raise ValueError("Probability must be between 0 and 1")
        if self.effect_ratio < 0 or self.effect_ratio > 1:
            raise ValueError("Effect ratio must be between 0 and 1")
