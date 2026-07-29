from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from aip.domain.analytics.ranking.ranking_result import RankingResult
from aip.domain.relative_value.enums.recommendation_type import RecommendationType
from aip.domain.relative_value.enums.valuation_status import ValuationStatus


@dataclass(frozen=True, slots=True)
class RelativeValueResult:
    """Immutable outcome of a relative-value evaluation."""

    instrument_id: str
    observed_market_price: Decimal
    theoretical_price: Decimal
    absolute_price_difference: Decimal
    percentage_price_difference: Decimal
    nominal_spread: Decimal
    benchmark_spread: Decimal
    interpolated_curve_spread: Decimal
    z_spread: Decimal
    rich_cheap_score: Decimal
    relative_value_score: Decimal
    confidence_score: Decimal
    ranking_result: RankingResult | None
    recommendation: RecommendationType
    policy_evaluation_summary: dict[str, object]
    decision_matrix: tuple[object, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    explanation: str | None = None
    calculation_timestamp: datetime | None = None
    calculation_identifier: str | None = None
    valuation_status: ValuationStatus = ValuationStatus.FAIR
