from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class InstitutionalPolicyProvider(ABC):
    """Port for retrieving institution-specific policy data."""

    @abstractmethod
    def get_policy_data(self, portfolio_reference: str) -> dict[str, Any]:
        raise NotImplementedError
