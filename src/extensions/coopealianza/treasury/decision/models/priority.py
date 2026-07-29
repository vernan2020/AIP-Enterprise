from __future__ import annotations

from enum import Enum


class PriorityLevel(str, Enum):
    """Priority levels for treasury recommendations."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
