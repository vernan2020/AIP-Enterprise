from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.engine.policy_engine import PolicyEngine
from aip.domain.policies.registry.policy_registry import PolicyRegistry
from aip.domain.policies.severity.policy_severity import PolicySeverity
from aip.domain.liquidity.hqla.models.hqla_policy_result import HQLAPolicyResult


class HQLAPolicyEngine:
    """Bridge the reusable policy engine into HQLA classification."""

    def __init__(self, registry: PolicyRegistry | None = None) -> None:
        self._engine = PolicyEngine(registry or PolicyRegistry())

    def evaluate(self, policies: tuple[object, ...], context: PolicyContext) -> HQLAPolicyResult:
        results = [self._engine.evaluate(policy, context) for policy in policies]
        total_score = sum((Decimal("1") if result.status == "PASSED" else Decimal("0") for result in results), Decimal("0"))
        return HQLAPolicyResult(policy_results=tuple(results), total_score=total_score)
