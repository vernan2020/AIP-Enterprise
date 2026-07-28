from __future__ import annotations

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.exceptions import PolicyValidationError


class PolicyRegistry:
    """In-memory registry for policies with deterministic lookup semantics."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    def register(self, policy: Policy) -> None:
        if policy.policy_id in self._policies:
            raise PolicyValidationError(f"Policy '{policy.policy_id}' is already registered")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> Policy:
        return self._policies[policy_id]

    def get_by_category(self, category: str) -> list[Policy]:
        return [policy for policy in self._policies.values() if policy.category == category]

    def get_by_tags(self, tags: tuple[str, ...]) -> list[Policy]:
        return [policy for policy in self._policies.values() if set(tags).issubset(set(policy.tags))]
