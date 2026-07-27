"""Valuation source enum."""

from enum import Enum


class ValuationSource(Enum):
    """Represents the source used for position valuation data."""

    MARKET_FEED = "market_feed"
    MANUAL = "manual"
    MODEL = "model"
    ADMIN_ADJUSTMENT = "admin_adjustment"
