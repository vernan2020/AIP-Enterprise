from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class ClassificationExclusionPolicy(InstitutionalPolicy):
    """Fail assets whose classifications match configured prefixes."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Exclude assets by classification prefix")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        classification = str(asset.get("classification", ""))
        if not classification:
            return self._result(context, "NOT_APPLICABLE", "Classification is missing")
        if any(classification.startswith(prefix) for prefix in self._config.excluded_classification_prefixes):
            return self._result(context, "FAILED", "Classification is excluded")
        return self._result(context, "PASSED", "Classification is allowed")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)
