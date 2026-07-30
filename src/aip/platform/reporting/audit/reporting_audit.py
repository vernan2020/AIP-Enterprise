from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Immutable audit record for a report execution."""

    report_id: str
    execution_id: str
    correlation_id: str
    renderer: str
    template: str
    duration_ms: int
    pages: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    timestamp: datetime


@dataclass(slots=True)
class ReportingAudit:
    """In-memory audit sink for reporting operations."""

    records: list[AuditRecord] = field(default_factory=list)

    def record(
        self,
        *,
        report_id: str,
        execution_id: str,
        correlation_id: str,
        renderer: str,
        template: str,
        duration_ms: int,
        pages: int,
        warnings: tuple[str, ...],
        errors: tuple[str, ...],
        timestamp: datetime,
    ) -> None:
        self.records.append(
            AuditRecord(
                report_id=report_id,
                execution_id=execution_id,
                correlation_id=correlation_id,
                renderer=renderer,
                template=template,
                duration_ms=duration_ms,
                pages=pages,
                warnings=warnings,
                errors=errors,
                timestamp=timestamp,
            )
        )
