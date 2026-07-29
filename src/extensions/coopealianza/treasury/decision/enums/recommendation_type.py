from __future__ import annotations

from enum import Enum


class RecommendationType(str, Enum):
    """Recommendation outcome for treasury decisions."""

    ACCUMULATE = "ACCUMULATE"
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    USE_AS_COLLATERAL = "USE_AS_COLLATERAL"
    DO_NOT_USE_AS_COLLATERAL = "DO_NOT_USE_AS_COLLATERAL"
    REDUCE_CONCENTRATION = "REDUCE_CONCENTRATION"
    IMPROVE_LIQUIDITY = "IMPROVE_LIQUIDITY"
    LIMIT_EXCESS_RISK = "LIMIT_EXCESS_RISK"
    MONITOR = "MONITOR"
    NO_ACTION = "NO_ACTION"
