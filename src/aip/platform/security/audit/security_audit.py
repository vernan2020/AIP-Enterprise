from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Immutable audit record."""

    event_type: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SecurityAudit:
    """Simple in-memory audit trail for security events."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(self, event_type: str, message: str, correlation_id: str | None = None, metadata: dict[str, Any] | None = None) -> AuditRecord:
        record = AuditRecord(event_type=event_type, message=message, correlation_id=correlation_id, metadata=dict(metadata or {}))
        self._records.append(record)
        return record

    def get_records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)
