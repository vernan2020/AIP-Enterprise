from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from src.extensions.coopealianza.treasury.decision.enums.recommendation_type import RecommendationType
from src.extensions.coopealianza.treasury.decision.models.impact_metrics import ImpactMetrics
from src.extensions.coopealianza.treasury.decision.models.priority import PriorityLevel


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Immutable recommendation emitted by the treasury decision engine."""

    recommendation_id: str
    instrument_id: str
    recommendation: RecommendationType
    priority: PriorityLevel
    score: Decimal
    confidence: Decimal
    explanation: str
    rationale: tuple[str, ...] = field(default_factory=tuple)
    policy_summary: dict[str, object] = field(default_factory=dict)
    rejected_alternatives: tuple[RecommendationType, ...] = field(default_factory=tuple)
    expected_impact: ImpactMetrics = field(default_factory=ImpactMetrics)
    policy_references: tuple[str, ...] = field(default_factory=tuple)
    affected_assets: tuple[str, ...] = field(default_factory=tuple)
    upstream_calculation_references: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    correlation_id: str = ""
    calculation_id: str = ""
    decision_horizon: str = "T+1"
