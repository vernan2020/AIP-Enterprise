from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class CollateralAvailabilityPolicy(InstitutionalPolicy):
    """Evaluate whether an asset is operationally available as collateral."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure collateral is operationally available")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        if asset.get("collateral_available") is True and asset.get("operationally_available") is not False:
            return self._result(context, "PASSED", "Asset is available as collateral")
        return self._result(context, "FAILED", "Asset is not collateral-available")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)
