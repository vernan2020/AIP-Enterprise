from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class MarketProvider(ABC):
    """Abstraction over external market-data providers."""

    @abstractmethod
    def get_spot_rate(self, currency: str, tenor: Decimal) -> Decimal:
        """Return the spot rate for the requested currency and tenor."""
