from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity

from ..policy_outcome import LiquidityPolicyOutcome


class LiquidityLimitPolicy(Policy):
    """Evaluate liquidity limit position against configured threshold."""

    def __init__(self, limit_ratio: Decimal) -> None:
        super().__init__(
            policy_id="coopealianza.liquidity.limits",
            name="Liquidity Limit",
            description="Ensures the liquidity position stays inside the configured limit",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="liquidity",
            reference=PolicyReference(source="coopealianza", identifier="liquidity-limit"),
            tags=("liquidity", "limits"),
        )
        self.limit_ratio = limit_ratio

    def evaluate_outcome(self, context: PolicyContext) -> LiquidityPolicyOutcome:
        ratio = context.metadata.get("liquidity_ratio") if context.metadata else None
        if ratio is None:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="WARNING",
                message="Liquidity ratio was not provided",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Provide the liquidity ratio before evaluating the limit",
            )
        if Decimal(str(ratio)) <= self.limit_ratio:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="PASS",
                message="Liquidity limit respected",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Maintain current liquidity management practices",
            )
        return LiquidityPolicyOutcome(
            policy_id=self.policy_id,
            status="FAIL",
            message="Liquidity limit breached",
            severity=self.severity,
            reference=self.reference,
            recommended_action="Reduce liquidity exposure or add reserves",
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        outcome = self.evaluate_outcome(context)
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED" if outcome.status == "PASS" else "FAIL" if outcome.status == "FAIL" else outcome.status,
            message=outcome.message,
            severity=outcome.severity,
            references=(outcome.reference,) if outcome.reference else (),
            timestamp=context.timestamp or context.timestamp,
            evaluation_duration=None,
            context_id=context.context_id,
        )
