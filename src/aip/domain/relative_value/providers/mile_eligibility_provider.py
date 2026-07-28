from __future__ import annotations

from abc import ABC, abstractmethod


class MILEligibilityProvider(ABC):
    """Protocol-like port for MILE eligibility."""

    @abstractmethod
    def is_eligible(self, instrument_id: str) -> bool:
        """Return whether the instrument is MILE eligible."""
