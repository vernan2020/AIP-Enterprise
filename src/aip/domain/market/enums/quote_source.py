from __future__ import annotations

from enum import Enum


class QuoteSource(str, Enum):
    """Supported market quote sources."""

    CENTRAL_BANK = "central_bank"
    BROKER = "broker"
    MARKET_MAKER = "market_maker"
    INTERNAL = "internal"
