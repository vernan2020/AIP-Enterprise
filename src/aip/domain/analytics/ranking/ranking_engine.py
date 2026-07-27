from __future__ import annotations

from decimal import Decimal

from aip.domain.analytics.enums.ranking_order import RankingOrder
from aip.domain.analytics.exceptions import DuplicateRankItemError, RankingError
from aip.domain.analytics.ranking.rank_item import RankItem
from aip.domain.analytics.ranking.ranking_result import RankingResult
from aip.domain.analytics.ranking.tie_breaker import TieBreaker


class RankingEngine:
    """Deterministic ranking engine with explicit tie handling."""

    def rank(
        self,
        items: list[RankItem],
        ranking_order: RankingOrder,
        tie_breaker: TieBreaker | None = None,
    ) -> RankingResult:
        if not items:
            raise RankingError("Ranking input cannot be empty")
        business_ids = [item.business_id for item in items]
        if len(set(business_ids)) != len(business_ids):
            raise DuplicateRankItemError("Duplicate business identifiers are not allowed")
        if ranking_order is RankingOrder.ASCENDING:
            ordered = sorted(items, key=lambda item: item.primary_score)
        else:
            ordered = sorted(items, key=lambda item: item.primary_score, reverse=True)
        if tie_breaker is not None:
            ordered = sorted(ordered, key=lambda item: item.primary_score, reverse=ranking_order is RankingOrder.DESCENDING)
            for index in range(len(ordered)):
                for inner in range(index + 1, len(ordered)):
                    if ordered[index].primary_score == ordered[inner].primary_score:
                        if tie_breaker.resolve(ordered[index], ordered[inner]) > 0:
                            ordered[index], ordered[inner] = ordered[inner], ordered[index]
        ordinal_rank = tuple(range(1, len(ordered) + 1))
        dense_rank = []
        last_score: Decimal | None = None
        current_dense = 0
        for item in ordered:
            if last_score is None or item.primary_score != last_score:
                current_dense += 1
            dense_rank.append(current_dense)
            last_score = item.primary_score
        percentile_rank = tuple(Decimal(rank) / Decimal(len(ordered)) for rank in ordinal_rank)
        tie_groups = []
        for index, item in enumerate(ordered):
            same_score = [candidate.business_id for candidate in ordered if candidate.primary_score == item.primary_score]
            tie_groups.append(tuple(same_score))
        return RankingResult(
            ranked_items=tuple(ordered),
            ordinal_rank=ordinal_rank,
            dense_rank=tuple(dense_rank),
            percentile_rank=percentile_rank,
            tie_groups=tuple(tie_groups),
            explanation=("Deterministic ranking with explicit tie handling",),
        )
