from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import LiquidityPolicyConfig
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class IssuerEligibilityPolicy(InstitutionalPolicy):
    """Evaluate whether the issuer category is eligible for institutional purposes."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure issuer category is eligible")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        issuer_category = str(asset.get("issuer_category", "")).strip()
        if not issuer_category:
            return self._result(context, "NOT_APPLICABLE", "Issuer category is missing")
        if issuer_category in self._config.issuer_categories:
            return self._result(context, "PASSED", "Issuer category is eligible")
        return self._result(context, "FAILED", "Issuer category is not eligible")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)
