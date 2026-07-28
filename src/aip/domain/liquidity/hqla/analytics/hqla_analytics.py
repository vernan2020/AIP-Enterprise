from __future__ import annotations

from decimal import Decimal
from typing import Iterable


class HQLAAnalytics:
    """Provide deterministic analytics for HQLA scoring."""

    def build(self, values: Iterable[Decimal | None], missing_count: int) -> dict[str, Decimal | int | bool]:
        scored_values = [value for value in values if value is not None]
        if not scored_values:
            return {"average_score": Decimal("0"), "missing_count": missing_count, "has_data": False}

        total = sum(scored_values, Decimal("0"))
        return {
            "average_score": total / Decimal(len(scored_values)),
            "missing_count": missing_count,
            "has_data": True,
        }
