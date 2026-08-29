from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity

from ..policy_outcome import LiquidityPolicyOutcome


class HQLAPolicy(Policy):
    """Evaluate high-quality liquid asset threshold policy."""

    def __init__(self, minimum_score: Decimal) -> None:
        super().__init__(
            policy_id="coopealianza.liquidity.hqla",
            name="HQLA Threshold",
            description="Ensures eligible assets meet the institutional HQLA threshold",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.HIGH,
            category="liquidity",
            reference=PolicyReference(source="coopealianza", identifier="hqla-threshold"),
            tags=("liquidity", "hqla"),
        )
        self.minimum_score = minimum_score

    def evaluate_outcome(self, context: PolicyContext) -> LiquidityPolicyOutcome:
        score = context.metadata.get("hqla_score") if context.metadata else None
        if score is None:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="WARNING",
                message="HQLA score was not provided",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Provide the HQLA score before issuing a liquidity decision",
            )
        if Decimal(str(score)) >= self.minimum_score:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="PASS",
                message="HQLA threshold met",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Maintain the current liquidity buffer",
            )
        return LiquidityPolicyOutcome(
            policy_id=self.policy_id,
            status="FAIL",
            message="HQLA threshold not met",
            severity=self.severity,
            reference=self.reference,
            recommended_action="Increase high-quality liquid assets or reduce liquidity drawdown",
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        outcome = self.evaluate_outcome(context)
        return EvaluationResult(
            policy_id=self.policy_id,
            status=(
                "PASSED"
                if outcome.status == "PASS"
                else "FAIL" if outcome.status == "FAIL" else outcome.status
            ),
            message=outcome.message,
            severity=outcome.severity,
            references=(outcome.reference,) if outcome.reference else (),
            timestamp=context.timestamp or context.timestamp,
            evaluation_duration=None,
            context_id=context.context_id,
        )
