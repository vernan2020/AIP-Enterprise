from __future__ import annotations

from enum import Enum


class HQLAClassification(str, Enum):
    """High-quality liquid asset classifications."""

    ELIGIBLE = "eligible"
    CONDITIONALLY_ELIGIBLE = "conditionally_eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNKNOWN = "unknown"
    INELIGIBLE = "not_eligible"
