from __future__ import annotations

from abc import ABC, abstractmethod


class CapitalConsumptionProvider(ABC):
    """Protocol-like port for capital consumption information."""

    @abstractmethod
    def get_consumption(self, instrument_id: str) -> float:
        """Return the capital consumption for the instrument."""
