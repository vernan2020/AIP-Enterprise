from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.analytics.enums.score_direction import ScoreDirection


@dataclass(frozen=True, slots=True)
class DecisionMatrix:
    """Immutable row in a relative-value decision matrix."""

    factor_id: str
    factor_label: str
    raw_value: Decimal
    unit: str
    normalized_value: Decimal
    configured_weight: Decimal
    effective_weight: Decimal
    contribution: Decimal
    direction: ScoreDirection
    evidence: str
    reference: str
    status: str
    warning: str | None = None
