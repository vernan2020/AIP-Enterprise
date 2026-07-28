from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aip.application.exceptions import ContractValidationError


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Application-level result for a workflow run."""

    workflow_id: str
    correlation_id: str
    status: str
    result: Any | None
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime | None = None
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    calculation_id: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    step_results: dict[str, Any] = field(default_factory=dict)
    domain_references: tuple[str, ...] = ()
    telemetry: Any | None = None

    def __post_init__(self) -> None:
        if not self.workflow_id or not str(self.workflow_id).strip():
            raise ContractValidationError("workflow_id is required")
        if not self.correlation_id or not str(self.correlation_id).strip():
            raise ContractValidationError("correlation_id is required")
        if not self.status or not str(self.status).strip():
            raise ContractValidationError("status is required")
        if self.executed_at is not None and self.executed_at.tzinfo is None:
            raise ContractValidationError("executed_at must be timezone-aware")
        if self.requested_at is not None and self.requested_at.tzinfo is None:
            raise ContractValidationError("requested_at must be timezone-aware")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ContractValidationError("completed_at must be timezone-aware")
        if self.requested_at is None and self.completed_at is None and self.executed_at is not None:
            object.__setattr__(self, "requested_at", self.executed_at)
        if self.completed_at is None and self.executed_at is not None:
            object.__setattr__(self, "completed_at", self.executed_at)
        if self.requested_at is not None and self.completed_at is not None and self.completed_at < self.requested_at:
            raise ContractValidationError("completed_at cannot be before requested_at")
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))
        object.__setattr__(self, "step_results", deepcopy(dict(self.step_results)))
