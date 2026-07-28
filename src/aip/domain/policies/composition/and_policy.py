from __future__ import annotations

from datetime import datetime, timezone

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.composition.composite_policy import CompositePolicy
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.severity.policy_severity import PolicySeverity


class AndPolicy(CompositePolicy):
    """Evaluates all child policies and requires every child to pass."""

    def __init__(self, children: tuple[Policy, ...]) -> None:
        super().__init__(
            children=children,
            policy_id="AND",
            name="AND",
            description="Requires all child policies to pass",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="composition",
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        results = []
        for child in self.children:
            child_result = child.evaluate(context)
            results.append(child_result)
            if child_result.status != "PASSED":
                return EvaluationResult(
                    policy_id=self.policy_id,
                    status=child_result.status,
                    message=f"AND policy failed due to {child.policy_id}",
                    severity=self.severity,
                    references=tuple(child_result.references),
                    timestamp=child_result.timestamp,
                    evaluation_duration=None,
                    context_id=context.context_id,
                )
        return EvaluationResult(
            policy_id=self.policy_id,
            status="PASSED",
            message="All child policies passed",
            severity=self.severity,
            references=(),
            timestamp=results[-1].timestamp if results else datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )
