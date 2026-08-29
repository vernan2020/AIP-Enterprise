from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class StartupStatus:
    """Structured status for a bootstrap step."""

    component_name: str
    status: str
    duration_seconds: float
    warning: str | None = None
    error: str | None = None
    correlation_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
