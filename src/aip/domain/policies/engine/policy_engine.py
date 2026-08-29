from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.base.policy_result import PolicyResult
from aip.domain.policies.evaluation.evaluation_report import EvaluationReport
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.exceptions import PolicyDependencyError
from aip.domain.policies.registry.policy_registry import PolicyRegistry


class PolicyEngine:
    """Domain engine for evaluating registered policies with dependency handling."""

    def __init__(self, registry: PolicyRegistry | None = None) -> None:
        self._registry = registry or PolicyRegistry()

    def register(self, policy: Policy) -> None:
        self._registry.register(policy)

    def evaluate(self, policy: Policy, context: PolicyContext) -> PolicyResult:
        result = self._evaluate_policy(policy, context, seen=())
        return result.to_policy_result()

    def evaluate_many(self, policies: Sequence[Policy], context: PolicyContext) -> EvaluationReport:
        ordered_policies = sorted(
            policies,
            key=lambda policy: (-policy.priority, policy.policy_id),
        )
        results = [self.evaluate(policy, context) for policy in ordered_policies]
        statuses = [result.status for result in results]
        if any(status == "FAILED" for status in statuses):
            overall_status = "FAILED"
            message = "One or more policies failed"
        elif any(status == "WARNING" for status in statuses):
            overall_status = "WARNING"
            message = "One or more policies emitted warnings"
        elif any(status == "NOT_APPLICABLE" for status in statuses):
            overall_status = "NOT_APPLICABLE"
            message = "All evaluated policies were not applicable"
        else:
            overall_status = "PASSED"
            message = "All policies passed"
        return EvaluationReport(
            results=tuple(results), overall_status=overall_status, message=message
        )

    def _evaluate_policy(
        self, policy: Policy, context: PolicyContext, seen: tuple[str, ...]
    ) -> EvaluationResult:
        if policy.policy_id in seen:
            raise PolicyDependencyError(f"Circular dependency detected for {policy.policy_id}")
        if not policy.enabled:
            return EvaluationResult(
                policy_id=policy.policy_id,
                status="NOT_APPLICABLE",
                message="Policy is disabled",
                severity=policy.severity,
                references=(),
                timestamp=datetime.now(timezone.utc),
                evaluation_duration=None,
                context_id=context.context_id,
            )
        for dependency_id in policy.dependencies:
            try:
                dependency = self._registry.get(dependency_id)
            except KeyError:
                return EvaluationResult(
                    policy_id=policy.policy_id,
                    status="NOT_APPLICABLE",
                    message=f"Missing dependency: {dependency_id}",
                    severity=policy.severity,
                    references=(),
                    timestamp=datetime.now(timezone.utc),
                    evaluation_duration=None,
                    context_id=context.context_id,
                )
            self._evaluate_policy(dependency, context, seen + (policy.policy_id,))
        return policy.evaluate(context)
