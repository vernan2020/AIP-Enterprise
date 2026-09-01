from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from time import perf_counter

from aip.domain.policies.base.policy_context import PolicyContext
from aip.domain.policies.evaluation.evaluation_result import EvaluationResult
from aip.domain.policies.exceptions import PolicyValidationError
from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity


class Policy(ABC):
    """Abstract policy definition with common metadata and evaluation behavior."""

    def __init__(
        self,
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
        priority: int = 0,
    ) -> None:
        if not policy_id or not name or not description or not version:
            raise PolicyValidationError(
                "Policy identifier, name, description, and version are required"
            )
        if not category:
            raise PolicyValidationError("Policy category is required")
        if not isinstance(severity, PolicySeverity):
            raise PolicyValidationError("Policy severity is invalid")

        self.policy_id = policy_id
        self.name = name
        self.description = description
        self.version = version
        self.enabled = enabled
        self.severity = severity
        self.category = category
        self.reference = reference
        self.tags = tuple(tags or ())
        self.dependencies = tuple(dependencies or ())
        self.priority = priority

    def evaluate(self, context: PolicyContext) -> EvaluationResult:
        if not self.enabled:
            return EvaluationResult(
                policy_id=self.policy_id,
                status="NOT_APPLICABLE",
                message="Policy is disabled",
                severity=self.severity,
                references=(),
                timestamp=datetime.now(timezone.utc),
                evaluation_duration=None,
                context_id=context.context_id,
            )

        start = perf_counter()
        result = self._evaluate_impl(context)
        duration = perf_counter() - start
        return EvaluationResult(
            policy_id=result.policy_id,
            status=result.status,
            message=result.message,
            severity=result.severity,
            references=result.references,
            timestamp=result.timestamp,
            evaluation_duration=duration,
            context_id=result.context_id,
        )

    @abstractmethod
    def _evaluate_impl(self, context: PolicyContext) -> EvaluationResult:
        raise AssertionError("Subclasses must implement _evaluate_impl")
