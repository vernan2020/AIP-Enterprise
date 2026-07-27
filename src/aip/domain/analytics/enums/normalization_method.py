from __future__ import annotations

from enum import Enum


class NormalizationMethod(str, Enum):
    """Supported normalization methods."""

    MIN_MAX = "min_max"
    Z_SCORE = "z_score"
    ROBUST = "robust"
    PERCENTILE_RANK = "percentile_rank"
