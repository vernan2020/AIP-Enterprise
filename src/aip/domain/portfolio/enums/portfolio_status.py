"""Portfolio lifecycle status enum."""

from enum import Enum


class PortfolioStatus(Enum):
    """Represents the operational status of a portfolio aggregate."""

    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
