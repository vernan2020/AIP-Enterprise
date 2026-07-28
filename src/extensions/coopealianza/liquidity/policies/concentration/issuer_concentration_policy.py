from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import LiquidityPolicyConfig
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalPolicyError
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class IssuerConcentrationPolicy(InstitutionalPolicy):
    """Evaluate current concentration against warning and blocking thresholds."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure issuer concentration is within configured thresholds")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        concentration = self._coerce_decimal(asset.get("current_concentration"))
        warning = self._config.concentration_warning_limit or Decimal("0")
        blocking = self._config.concentration_blocking_limit or Decimal("0")
        if concentration < warning:
            return self._result(context, "PASSED", "Concentration is within warning threshold")
        if concentration < blocking:
            return self._result(context, "WARNING", "Concentration is approaching blocking threshold")
        return self._result(context, "FAILED", "Concentration exceeds blocking threshold")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)

    def _coerce_decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        raise InstitutionalPolicyError("Expected a numeric concentration value")

