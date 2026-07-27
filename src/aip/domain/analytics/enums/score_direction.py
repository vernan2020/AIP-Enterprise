from __future__ import annotations

from enum import Enum


class ScoreDirection(str, Enum):
    """Supported score directions."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    TARGET_IS_BEST = "target_is_best"
    NEUTRAL = "neutral"
