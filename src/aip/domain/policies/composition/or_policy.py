from __future__ import annotations

from datetime import datetime, timezone

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.composition.composite_policy import CompositePolicy
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.severity.policy_severity import PolicySeverity


class OrPolicy(CompositePolicy):
    """Evaluates child policies until one passes."""

    def __init__(self, children: tuple[Policy, ...]) -> None:
        super().__init__(
            children=children,
            policy_id="OR",
            name="OR",
            description="Passes if any child policy passes",
            version="1.0",
            enabled=True,
            severity=PolicySeverity.MEDIUM,
            category="composition",
        )

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        for child in self.children:
            child_result = child.evaluate(context)
            if child_result.status == "PASSED":
                return EvaluationResult(
                    policy_id=self.policy_id,
                    status="PASSED",
                    message=f"OR policy passed via {child.policy_id}",
                    severity=self.severity,
                    references=tuple(child_result.references),
                    timestamp=child_result.timestamp,
                    evaluation_duration=None,
                    context_id=context.context_id,
                )
        return EvaluationResult(
            policy_id=self.policy_id,
            status="FAILED",
            message="No child policy passed",
            severity=self.severity,
            references=(),
            timestamp=context.timestamp or datetime.now(timezone.utc),
            evaluation_duration=None,
            context_id=context.context_id,
        )
