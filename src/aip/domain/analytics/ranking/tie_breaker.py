from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from aip.domain.analytics.enums.ranking_order import RankingOrder
from aip.domain.analytics.exceptions import RankingError
from aip.domain.analytics.ranking.rank_item import RankItem


@dataclass(frozen=True, slots=True)
class TieBreaker:
    """Configurable tie-breaker strategy for ranking."""

    metric_name: str | None = None
    business_id_first: bool = True
    ranking_order: RankingOrder = RankingOrder.DESCENDING

    def resolve(self, left: RankItem, right: RankItem) -> int:
        if self.business_id_first:
            if left.business_id < right.business_id:
                return -1
            if left.business_id > right.business_id:
                return 1
        if self.metric_name is None:
            return 0
        for left_metric, right_metric in zip(left.secondary_metrics, right.secondary_metrics):
            if left_metric[0] == self.metric_name:
                if left_metric[1] < right_metric[1]:
                    return -1 if self.ranking_order is RankingOrder.ASCENDING else 1
                if left_metric[1] > right_metric[1]:
                    return 1 if self.ranking_order is RankingOrder.ASCENDING else -1
        raise RankingError("Tie breaker metric was not found")
