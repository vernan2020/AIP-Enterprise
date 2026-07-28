from __future__ import annotations

from abc import ABC, abstractmethod

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.base.policy_result import PolicyResult


class PolicyProvider(ABC):
    """Protocol-like port for policy evaluation."""

    @abstractmethod
    def evaluate(self, context: PolicyContext) -> PolicyResult:
        """Evaluate the supplied policy context."""
