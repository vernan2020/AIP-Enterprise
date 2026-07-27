from __future__ import annotations

from enum import Enum


class MarketType(str, Enum):
    """Supported market categories for market data snapshots."""

    GOVERNMENT = "government"
    INTERBANK = "interbank"
    MONEY_MARKET = "money_market"
    OTC = "otc"
