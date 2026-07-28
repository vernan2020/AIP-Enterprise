from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aip.domain.policies.metadata.policy_reference import PolicyReference
from aip.domain.policies.severity.policy_severity import PolicySeverity


@dataclass(frozen=True, slots=True)
class LiquidityPolicyOutcome:
    """Institution-specific representation of policy outcome semantics."""

    policy_id: str
    status: str
    message: str
    severity: PolicySeverity
    reference: PolicyReference | None = None
    recommended_action: str | None = None
    metadata: dict[str, Any] | None = None
