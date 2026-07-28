from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import LiquidityPolicyConfig
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalPolicyError
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class MinimumLiquidityPolicy(InstitutionalPolicy):
    """Evaluate a supplied liquidity metric against configured thresholds."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure liquidity metric stays above configured thresholds")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        metric = self._coerce_decimal(asset.get("liquidity_metric"))
        if metric >= (self._config.minimum_liquidity_warning or Decimal("0")):
            return self._result(context, "PASSED", "Liquidity metric is above warning threshold")
        if metric >= (self._config.minimum_liquidity_blocking or Decimal("0")):
            return self._result(context, "WARNING", "Liquidity metric is below warning threshold")
        return self._result(context, "FAILED", "Liquidity metric is below blocking threshold")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)

    def _coerce_decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        raise InstitutionalPolicyError("Expected a numeric liquidity metric")

