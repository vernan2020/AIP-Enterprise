from __future__ import annotations

from enum import Enum


class ValuationStatus(str, Enum):
    """Relative-value valuation status."""

    RICH = "RICH"
    FAIR = "FAIR"
    CHEAP = "CHEAP"
