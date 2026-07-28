from __future__ import annotations

from decimal import Decimal

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity

from ..policy_outcome import LiquidityPolicyOutcome


class ConcentrationPolicy(Policy):
    """Evaluate exposure concentration against configured threshold."""

    def __init__(self, concentration_ratio: Decimal) -> None:
        super().__init__(
            policy_id="coopealianza.liquidity.concentration",
            name="Concentration Limit",
            description="Ensures concentration risk remains within the configured tolerance",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="liquidity",
            reference=PolicyReference(source="coopealianza", identifier="concentration-limit"),
            tags=("liquidity", "concentration"),
        )
        self.concentration_ratio = concentration_ratio

    def evaluate_outcome(self, context: PolicyContext) -> LiquidityPolicyOutcome:
        ratio = context.metadata.get("concentration_ratio") if context.metadata else None
        if ratio is None:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="WARNING",
                message="Concentration ratio was not provided",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Provide the concentration ratio before approving the position",
            )
        if Decimal(str(ratio)) <= self.concentration_ratio:
            return LiquidityPolicyOutcome(
                policy_id=self.policy_id,
                status="PASS",
                message="Concentration limit respected",
                severity=self.severity,
                reference=self.reference,
                recommended_action="Maintain current portfolio diversification",
            )
        return LiquidityPolicyOutcome(
            policy_id=self.policy_id,
            status="FAIL",
            message="Concentration limit breached",
            severity=self.severity,
            reference=self.reference,
            recommended_action="Reduce concentration or rebalance the portfolio",
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
