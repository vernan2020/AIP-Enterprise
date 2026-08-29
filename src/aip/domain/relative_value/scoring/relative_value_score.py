from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.enums.score_direction import ScoreDirection
from aip.domain.analytics.exceptions import InvalidWeightError
from aip.domain.analytics.scoring.score_band import ScoreBand


@dataclass(frozen=True, slots=True)
class RelativeValueScore:
    """Calculate a deterministic weighted score from configurable components."""

    raw_values: dict[str, Decimal]
    weights: dict[str, Decimal]
    directions: dict[str, ScoreDirection]
    bands: dict[str, tuple[ScoreBand, ...]] | None = None

    def __post_init__(self) -> None:
        if not self.raw_values:
            raise InvalidWeightError("At least one component is required")
        if set(self.raw_values) != set(self.weights) or set(self.raw_values) != set(
            self.directions
        ):
            raise InvalidWeightError("Weights and directions must align with input values")
        total_weight = sum(self.weights.values(), Decimal("0"))
        if total_weight <= 0:
            raise InvalidWeightError("Total weight must be positive")
        if any(weight < 0 for weight in self.weights.values()):
            raise InvalidWeightError("Weights cannot be negative")
        if len(self.raw_values) < 2:
            raise InvalidWeightError("At least two components are required")

    @property
    def final_score(self) -> Decimal:
        normalized_total = Decimal("0")
        total_weight = sum(self.weights.values(), Decimal("0"))
        for name, raw_value in self.raw_values.items():
            weight = self.weights[name]
            direction = self.directions[name]
            normalized = self._normalize(raw_value, name, direction)
            normalized_total += normalized * weight
        return normalized_total / total_weight

    def _normalize(self, raw_value: Decimal, name: str, direction: ScoreDirection) -> Decimal:
        if direction is ScoreDirection.LOWER_IS_BETTER:
            return Decimal("1") - raw_value
        if direction is ScoreDirection.HIGHER_IS_BETTER:
            return raw_value
        return raw_value

    @property
    def component_contributions(self) -> dict[str, Decimal]:
        return {
            name: self._normalize(raw_value, name, self.directions[name]) * self.weights[name]
            for name, raw_value in self.raw_values.items()
        }
