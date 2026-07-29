from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.domain.analytics.explainability.explanation import Explanation
from src.extensions.coopealianza.treasury.decision.models.recommendation import Recommendation
from src.extensions.coopealianza.treasury.decision.models.recommendation_group import RecommendationGroup


@dataclass(frozen=True, slots=True)
class TreasuryDecisionResult:
    """Output object for treasury decision generation."""

    portfolio_reference: str
    recommendations: tuple[Recommendation, ...]
    recommendation_groups: tuple[RecommendationGroup, ...]
    summary: dict[str, Any] = field(default_factory=dict)
    explanation: Explanation | None = None
    calculation_identifier: str = ""
    correlation_id: str = ""
