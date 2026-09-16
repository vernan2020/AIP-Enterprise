from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..exceptions import InvalidWeightError
from .score_component import ScoreComponent


@dataclass(frozen=True, slots=True)
class WeightedScore:
    """Immutable weighted score result."""

    final_score: Decimal
    total_effective_weight: Decimal
    component_contributions: tuple[ScoreComponent, ...]
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.total_effective_weight == 0:
            raise InvalidWeightError("Total effective weight must be non-zero")
