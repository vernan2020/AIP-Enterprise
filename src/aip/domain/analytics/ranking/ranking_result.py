from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.ranking.rank_item import RankItem


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Immutable ranking result with deterministic rank information."""

    ranked_items: tuple[RankItem, ...]
    ordinal_rank: tuple[int, ...]
    dense_rank: tuple[int, ...]
    percentile_rank: tuple[Decimal, ...]
    tie_groups: tuple[tuple[str, ...], ...]
    explanation: tuple[str, ...] = ()
