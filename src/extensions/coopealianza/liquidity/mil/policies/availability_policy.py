from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.mil.configuration.mil_policy_config import (
    MilPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class AvailabilityPolicy(InstitutionalPolicy):
    def __init__(self, config: MilPolicyConfig) -> None:
        super().__init__(
            config,  # type: ignore[arg-type]
            description="Ensure asset is operationally available",
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        available = bool(asset.get("operational_availability", False))
        if available:
            return self._result(context, "PASSED", "Asset is operationally available")
        return self._result(context, "FAILED", "Asset is unavailable")
