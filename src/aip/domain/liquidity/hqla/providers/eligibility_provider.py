from __future__ import annotations

from abc import ABC, abstractmethod


class EligibilityProvider(ABC):
    """Typed port for eligibility determination."""

    @abstractmethod
    def is_eligible(self, instrument_id: str) -> bool:
        """Return whether the instrument is eligible for the managed classification."""
