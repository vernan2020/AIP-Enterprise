from __future__ import annotations

from enum import Enum


class RankingOrder(str, Enum):
    """Supported ranking directions."""

    ASCENDING = "ascending"
    DESCENDING = "descending"
