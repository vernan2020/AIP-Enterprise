from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class EncumbrancePolicy(InstitutionalPolicy):
    """Evaluate whether the asset is encumbered based on configured status."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure asset encumbrance status is acceptable")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        status_value = str(asset.get("encumbrance_status", "")).strip().lower()
        if status_value in self._config.required_encumbrance_status:
            return self._result(context, "PASSED", "Encumbrance status is acceptable")
        return self._result(context, "FAILED", "Encumbrance status is not acceptable")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)
