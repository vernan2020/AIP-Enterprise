from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from aip.domain.relative_value.enums.recommendation_type import RecommendationType


@dataclass(frozen=True, slots=True)
class InvestmentOpportunity:
    """Immutable investment opportunity used for ranking."""

    business_id: str
    score: Decimal
    recommendation: RecommendationType = RecommendationType.HOLD
    metadata: dict[str, object] = field(default_factory=dict)
