from __future__ import annotations

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.severity.policy_severity import PolicySeverity


class NotPolicy(Policy):
    """Inverts the child policy result."""

    def __init__(self, child: Policy) -> None:
        super().__init__(
            policy_id=f"NOT:{child.policy_id}",
            name=f"Not {child.name}",
            description=f"Inverts {child.policy_id}",
            version=child.version,
            enabled=child.enabled,
            severity=child.severity,
            category=child.category,
            reference=child.reference,
            tags=child.tags,
            dependencies=child.dependencies,
        )
        self.child = child

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        child_result = self.child.evaluate(context)
        if child_result.status == "PASSED":
            return EvaluationResult(
                policy_id=self.policy_id,
                status="FAILED",
                message="Child policy passed",
                severity=self.severity,
                references=tuple(child_result.references),
                timestamp=child_result.timestamp,
                evaluation_duration=None,
                context_id=context.context_id,
            )
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED",
            message="Child policy did not pass",
            severity=self.severity,
            references=tuple(child_result.references),
            timestamp=child_result.timestamp,
            evaluation_duration=None,
            context_id=context.context_id,
        )
