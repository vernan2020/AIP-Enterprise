from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RankItem:
    """An immutable entity that can participate in ranking."""

    business_id: str
    primary_score: Decimal
    secondary_metrics: tuple[tuple[str, Decimal], ...] = ()
    metadata: dict[str, object] | None = None
