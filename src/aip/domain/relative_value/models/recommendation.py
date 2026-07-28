from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from aip.domain.relative_value.enums.recommendation_type import RecommendationType


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Immutable recommendation value object."""

    instrument_id: str
    recommendation: RecommendationType
    score: Decimal
    confidence: Decimal
    explanation: str
    policy_summary: dict[str, object] = field(default_factory=dict)
