from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.enums.score_direction import ScoreDirection
from aip.domain.analytics.exceptions import ScoringError


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """Immutable score component with validated thresholds and scale."""

    component_name: str
    raw_value: Decimal
    normalized_value: Decimal
    weight: Decimal
    score_direction: ScoreDirection
    contribution: Decimal
    minimum_threshold: Decimal | None = None
    maximum_threshold: Decimal | None = None
    target_value: Decimal | None = None
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not self.component_name.strip():
            raise ScoringError("Component name is required")
        if self.weight < 0:
            raise ScoringError("Weight must be non-negative")
        if self.normalized_value < Decimal("0") or self.normalized_value > Decimal("1"):
            raise ScoringError("Normalized value must be between 0 and 1")
        if self.score_direction is ScoreDirection.TARGET_IS_BEST and self.target_value is None:
            raise ScoringError("Target-based scoring requires a target value")
        if self.minimum_threshold is not None and self.maximum_threshold is not None:
            if self.minimum_threshold > self.maximum_threshold:
                raise ScoringError("Minimum threshold must be less than or equal to maximum threshold")
