from __future__ import annotations

from abc import ABC, abstractmethod


class MarketabilityProvider(ABC):
    """Typed port for marketability signals."""

    @abstractmethod
    def assess(self, instrument_id: str) -> dict[str, object]:
        """Return a marketability assessment payload."""
