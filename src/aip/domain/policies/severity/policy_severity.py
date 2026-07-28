from __future__ import annotations

from enum import Enum


class PolicySeverity(Enum):
    """Ordered policy severity values."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    def rank(self) -> int:
        return {
            PolicySeverity.INFO: 0,
            PolicySeverity.LOW: 1,
            PolicySeverity.MEDIUM: 2,
            PolicySeverity.HIGH: 3,
            PolicySeverity.CRITICAL: 4,
        }[self]
