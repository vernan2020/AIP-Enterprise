from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.analytics.explainability.explanation import Explanation
from aip.domain.liquidity.hqla.enums import HQLAClassification


@dataclass(frozen=True, slots=True)
class HQLAResult:
    """Immutable result for an HQLA evaluation."""

    valuation_date: date
    instrument_id: str | None
    classification: HQLAClassification
    eligible: bool
    score: Decimal
    reason: str
    analytics: dict[str, Decimal | int | bool]
    explanation: Explanation
    currency: str = "USD"
