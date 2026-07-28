from __future__ import annotations

from abc import ABC, abstractmethod


class LiquidityImpactProvider(ABC):
    """Protocol-like port for liquidity impact information."""

    @abstractmethod
    def get_liquidity_impact(self, instrument_id: str) -> float:
        """Return a liquidity impact score for the instrument."""
