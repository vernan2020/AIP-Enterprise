from __future__ import annotations

from dataclasses import dataclass

from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation


@dataclass(frozen=True, slots=True)
class RecommendationGroup:
    """A priority-grouped collection of recommendations."""

    group_name: str
    recommendations: tuple[Recommendation, ...]
    priority: int
