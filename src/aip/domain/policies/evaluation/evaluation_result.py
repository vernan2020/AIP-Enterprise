from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity

if TYPE_CHECKING:
    from aip.domain.policies.base.policy_result import PolicyResult


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Evaluation result for an individual policy."""

    policy_id: str
    status: str
    message: str
    severity: PolicySeverity
    references: tuple[PolicyReference, ...]
    timestamp: datetime
    evaluation_duration: float | None
    context_id: str

    def to_policy_result(self) -> "PolicyResult":
        from aip.domain.policies.base.policy_result import PolicyResult as PolicyResultType

        return PolicyResultType(
            policy_id=self.policy_id,
            status=self.status,
            message=self.message,
            severity=self.severity,
            references=self.references,
            timestamp=self.timestamp,
            evaluation_duration=self.evaluation_duration,
            context_id=self.context_id,
        )
