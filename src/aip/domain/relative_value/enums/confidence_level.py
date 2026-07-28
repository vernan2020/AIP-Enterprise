from __future__ import annotations

from enum import Enum


class ConfidenceLevel(str, Enum):
    """Confidence levels for recommendations."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
