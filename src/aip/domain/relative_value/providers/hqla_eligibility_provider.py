from __future__ import annotations

from abc import ABC, abstractmethod


class HQLAEligibilityProvider(ABC):
    """Protocol-like port for HQLA eligibility."""

    @abstractmethod
    def is_eligible(self, instrument_id: str) -> bool:
        """Return whether the instrument is HQLA eligible."""
