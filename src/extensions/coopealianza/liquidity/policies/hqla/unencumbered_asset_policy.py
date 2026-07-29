from __future__ import annotations

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.severity.policy_severity import PolicySeverity
from src.extensions.coopealianza.liquidity.configuration.liquidity_policy_config import (
    LiquidityPolicyConfig,
)
from src.extensions.coopealianza.liquidity.policies.institutional_policy import InstitutionalPolicy


class UnencumberedAssetPolicy(InstitutionalPolicy):
    """Evaluate whether an asset is available and not encumbered."""

    def __init__(self, config: LiquidityPolicyConfig) -> None:
        super().__init__(config, description="Ensure assets are unencumbered and available")

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        asset = self._coerce_asset(context)
        status = "PASSED"
        message = "Asset is unencumbered"
        severity = self.severity
        encumbrance_status = asset.get("encumbrance_status")
        if encumbrance_status == "unencumbered":
            status = "PASSED"
        elif encumbrance_status == "unknown":
            status = "WARNING"
            message = "Encumbrance status is unknown"
        else:
            status = "FAILED"
            message = "Asset is encumbered or unavailable"
            severity = PolicySeverity.CRITICAL

        return self._result(context, status, message, severity=severity)
