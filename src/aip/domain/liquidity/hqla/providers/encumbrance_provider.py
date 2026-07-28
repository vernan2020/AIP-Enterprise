from __future__ import annotations

from abc import ABC, abstractmethod


class EncumbranceProvider(ABC):
    """Typed port for encumbrance information."""

    @abstractmethod
    def assess(self, instrument_id: str) -> dict[str, object]:
        """Return an encumbrance assessment payload."""
