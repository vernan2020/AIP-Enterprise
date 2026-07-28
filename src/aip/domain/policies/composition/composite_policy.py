from __future__ import annotations

from aip.domain.policies.base.policy import Policy
from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.exceptions import PolicyValidationError
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity


class CompositePolicy(Policy):
    """Abstract policy composed of child policies."""

    def __init__(
        self,
        children: tuple[Policy, ...],
        policy_id: str,
        name: str,
        description: str,
        version: str,
        enabled: bool,
        severity: PolicySeverity,
        category: str,
        reference: PolicyReference | None = None,
        tags: tuple[str, ...] | None = None,
        dependencies: tuple[str, ...] | None = None,
    ) -> None:
        if not children:
            raise PolicyValidationError("Composite policy requires at least one child")
        super().__init__(
            policy_id=policy_id,
            name=name,
            description=description,
            version=version,
            enabled=enabled,
            severity=severity,
            category=category,
            reference=reference,
            tags=tags,
            dependencies=dependencies,
        )
        self.children = children

    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        raise AssertionError("Subclasses must implement _evaluate_impl")
