from __future__ import annotations

from abc import ABC, abstractmethod


class AccountingClassificationProvider(ABC):
    """Protocol-like port for accounting classification."""

    @abstractmethod
    def get_classification(self, instrument_id: str) -> str:
        """Return the accounting classification for the instrument."""
