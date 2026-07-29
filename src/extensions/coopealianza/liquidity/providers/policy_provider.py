from __future__ import annotations

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.engine.policy_engine import PolicyEngine
from aip.domain.policies.registry.policy_registry import PolicyRegistry

from ..configuration.models import CoopealianzaLiquiditySettings
from ..policies.concentration import ConcentrationPolicy
from ..policies.hqla import HQLAPolicy
from ..policies.issuer_limits import IssuerLimitPolicy
from ..policies.liquidity_limits import LiquidityLimitPolicy
from ..policies.mil import MILPolicy
from ..reports.policy_report import CoopealianzaLiquidityPolicyReport


class CoopealianzaLiquidityPolicyProvider:
    """Build institution-specific liquidity policies using the reusable policy engine."""

    def __init__(self, settings: CoopealianzaLiquiditySettings | None = None) -> None:
        self._settings = settings or CoopealianzaLiquiditySettings()
        self._registry = PolicyRegistry()
        self._engine = PolicyEngine(self._registry)
        self._policies = self._build_policies()
        for policy in self._policies:
            self._engine.register(policy)

    @property
    def engine(self) -> PolicyEngine:
        return self._engine

    @property
    def policies(self) -> tuple[Policy, ...]:
        return tuple(self._policies)

    def evaluate_many(self, context: PolicyContext) -> CoopealianzaLiquidityPolicyReport:
        report = self._engine.evaluate_many(self._policies, context)
        outcomes = tuple(policy.evaluate_outcome(context) for policy in self._policies)
        return CoopealianzaLiquidityPolicyReport.from_evaluation_report(report, outcomes)

    def _build_policies(self) -> tuple[Policy, ...]:
        return (
            HQLAPolicy(self._settings.thresholds.hqla_minimum_score),
            MILPolicy(self._settings.thresholds.mil_minimum_ratio),
            LiquidityLimitPolicy(self._settings.thresholds.liquidity_limit_ratio),
            IssuerLimitPolicy(self._settings.thresholds.issuer_limit_ratio),
            ConcentrationPolicy(self._settings.thresholds.concentration_ratio),
        )
