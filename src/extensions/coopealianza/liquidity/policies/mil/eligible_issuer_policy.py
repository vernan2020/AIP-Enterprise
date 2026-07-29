from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class EligibleIssuerPolicy(InstitutionalPolicy):
    """Evaluate configured issuer classes accepted for collateral purposes."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure issuer class is eligible for collateral")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        issuer_class = str(asset.get("issuer_class", "")).strip()
        if not issuer_class:
            return self._result(context, "NOT_APPLICABLE", "Issuer class is missing")
        if issuer_class in {"AA", "A"}:
            return self._result(context, "PASSED", "Issuer class is acceptable")
        return self._result(context, "FAILED", "Issuer class is not acceptable")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)
