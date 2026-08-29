from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.exceptions import InstitutionalPolicyError
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class MarketabilityPolicy(InstitutionalPolicy):
    """Evaluate configured marketability and price-availability requirements."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure marketability and price availability thresholds are met")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        missing_attributes = [attribute for attribute in self._config.required_marketability_attributes if attribute not in asset]
        if missing_attributes:
            return self._result(context, "FAILED", "Required marketability attributes are missing")
        self._coerce_decimal(asset.get("marketability_score"))
        self._coerce_decimal(asset.get("price_availability_score"))
        if self._is_stale(asset):
            return self._result(context, "WARNING", "Price data is stale")
        return self._result(context, "PASSED", "Marketability and price availability are sufficient")

    def _result(self, context: PolicyContext, status: str, message: str) -> EvaluationResult:
        return super()._result(context, status, message)

    def _coerce_decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        raise InstitutionalPolicyError("Expected a numeric marketability value")

    def _is_stale(self, asset: dict[str, object]) -> bool:
        price_timestamp = asset.get("price_timestamp")
        if not isinstance(price_timestamp, date):
            return False
        return price_timestamp < date.today()
