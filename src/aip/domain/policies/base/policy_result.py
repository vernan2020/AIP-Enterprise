from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity


@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Immutable result emitted by a policy evaluation."""

    policy_id: str
    status: str
    message: str
    severity: PolicySeverity
    references: tuple[PolicyReference, ...]
    timestamp: datetime
    evaluation_duration: float | None
    context_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "status": self.status,
            "message": self.message,
            "severity": self.severity.value,
            "references": [
                {
                    "source": reference.source,
                    "identifier": reference.identifier,
                    "url": reference.url,
                }
                for reference in self.references
            ],
            "timestamp": self.timestamp.isoformat(),
            "evaluation_duration": self.evaluation_duration,
            "context_id": self.context_id,
        }
