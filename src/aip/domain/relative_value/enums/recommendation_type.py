from __future__ import annotations

from enum import Enum


class RecommendationType(str, Enum):
    """Allowed recommendations for relative-value decisions."""

    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    REVIEW = "REVIEW"
