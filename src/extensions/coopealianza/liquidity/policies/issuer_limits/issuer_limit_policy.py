from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import LiquidityPolicyConfig
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalPolicyError
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class IssuerLimitPolicy(InstitutionalPolicy):
    """Evaluate current exposure against a configured issuer limit."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure issuer exposure stays within configured limit")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        exposure = self._coerce_decimal(asset.get("current_exposure"))
        limit = self._config.issuer_limit or Decimal("0")
        if exposure < limit:
            return self._result(context, "PASSED", "Exposure is below issuer limit")
        if exposure < limit * Decimal("1.5"):
            return self._result(context, "WARNING", "Exposure is approaching issuer limit")
        return self._result(context, "FAILED", "Exposure exceeds issuer limit")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)

    def _coerce_decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        raise InstitutionalPolicyError("Expected a numeric exposure value")

