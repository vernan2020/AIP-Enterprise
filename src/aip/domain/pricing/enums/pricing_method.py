from __future__ import annotations

from enum import Enum


class PricingMethod(str, Enum):
    """Supported pricing methods."""

    MARKET_VALUE = "market_value"
    YIELD_TO_MATURITY = "yield_to_maturity"
    PRESENT_VALUE = "present_value"
