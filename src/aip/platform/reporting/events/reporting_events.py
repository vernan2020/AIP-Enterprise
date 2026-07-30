from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class ReportingEvent:
    """Base event for reporting operations."""

    report_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ReportStarted(ReportingEvent):
    pass


@dataclass(frozen=True, slots=True)
class ReportCompleted(ReportingEvent):
    pass


@dataclass(frozen=True, slots=True)
class ReportFailed(ReportingEvent):
    error: str = ""


@dataclass(frozen=True, slots=True)
class ExportStarted(ReportingEvent):
    pass


@dataclass(frozen=True, slots=True)
class ExportCompleted(ReportingEvent):
    pass


@dataclass(frozen=True, slots=True)
class RetryStarted(ReportingEvent):
    attempt: int = 0


@dataclass(frozen=True, slots=True)
class RetryCompleted(ReportingEvent):
    attempt: int = 0
