from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity

from ..policy_outcome import LiquidityPolicyOutcome


class MILPolicy(Policy):
    """Evaluate minimum liquidity threshold policy."""

    def __init__(self, minimum_ratio: Decimal) -> None:
        super().__init__(
            policy_id="coopealianza.liquidity.mil",
            name="MIL Threshold",
            description="Ensures liquid asset coverage meets the minimum liquidity requirement",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.HIGH,
            category="liquidity",
            reference=PolicyReference(source="coopealianza", identifier="mil-threshold"),
            tags=("liquidity", "mil"),
        )
        self.minimum_ratio = minimum_ratio

    def evaluate_outcome(self, context: PolicyContext) -> LiquidityPolicyOutcome:
        ratio = context.metadata.get("mil_ratio") if context.metadata else None
        if ratio is None:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="WARNING",
                message="MIL ratio was not provided",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Provide the MIL ratio before evaluating liquidity adequacy",
            )
        if Decimal(str(ratio)) >= self.minimum_ratio:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="PASS",
                message="MIL threshold met",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Maintain the current liquidity coverage",
            )
        return LiquidityPolicyOutcome(
            policy_id=self.policy_id,
            status="FAIL",
            message="MIL threshold not met",
            severity=self.severity,
            reference=self.reference,
            recommended_action="Increase liquid asset availability",
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
