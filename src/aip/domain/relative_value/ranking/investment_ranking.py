from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.enums.ranking_order import RankingOrder
from aip.domain.analytics.ranking.rank_item import RankItem
from aip.domain.analytics.ranking.ranking_engine import RankingEngine
from aip.domain.analytics.ranking.ranking_result import RankingResult
from aip.domain.analytics.ranking.tie_breaker import TieBreaker
from aip.domain.relative_value.models.investment_opportunity import InvestmentOpportunity


@dataclass(frozen=True, slots=True)
class InvestmentRanking:
    """Rank opportunities with deterministic ordering and explicit tie handling."""

    def rank(self, opportunities: tuple[InvestmentOpportunity, ...]) -> RankingResult:
        if not opportunities:
            raise ValueError("Opportunities cannot be empty")
        business_ids = [opportunity.business_id for opportunity in opportunities]
        if len(set(business_ids)) != len(business_ids):
            raise ValueError("Duplicate business identifiers are not allowed")
        items = [
            RankItem(
                business_id=opportunity.business_id,
                primary_score=opportunity.score,
                secondary_metrics=(
                    (
                        "recommendation",
                        Decimal(1) if opportunity.recommendation is not None else Decimal(0),
                    ),
                ),
                metadata=opportunity.metadata,
            )
            for opportunity in opportunities
        ]
        result = RankingEngine().rank(
            items,
            RankingOrder.DESCENDING,
            TieBreaker(metric_name="recommendation", ranking_order=RankingOrder.ASCENDING),
        )
        percentile_rank = tuple(
            Decimal("1") - (Decimal(index) / Decimal(len(result.ranked_items)))
            for index in range(len(result.ranked_items))
        )
        return RankingResult(
            ranked_items=result.ranked_items,
            ordinal_rank=result.ordinal_rank,
            dense_rank=result.dense_rank,
            percentile_rank=percentile_rank,
            tie_groups=result.tie_groups,
            explanation=result.explanation,
        )
