"""Position status enum."""

from enum import Enum


class PositionStatus(Enum):
    """Represents the lifecycle state of a portfolio position."""

    OPEN = "open"
    CLOSED = "closed"
