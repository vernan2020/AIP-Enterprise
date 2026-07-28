from __future__ import annotations

from abc import ABC, abstractmethod


class IssuerLimitProvider(ABC):
    """Protocol-like port for issuer-limit checks."""

    @abstractmethod
    def get_limit(self, issuer_id: str) -> float:
        """Return the configured issuer limit."""
