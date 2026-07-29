from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from aip.platform.scheduler.jobs.job_priority import JobPriority
from aip.platform.scheduler.triggers.manual_trigger import ManualTrigger


Handler = Callable[["ScheduledJob", dict[str, Any] | None], dict[str, Any]]


@dataclass(slots=True)
class ScheduledJob:
    job_id: str
    name: str
    handler: Handler
    trigger: ManualTrigger | None = None
    priority: JobPriority = JobPriority.NORMAL
    dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    retries: int = 0
    timeout_seconds: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
