from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SchedulerEventType(str, Enum):
    SCHEDULER_STARTED = "scheduler_started"
    SCHEDULER_STOPPED = "scheduler_stopped"
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    RETRY_STARTED = "retry_started"
    RETRY_COMPLETED = "retry_completed"
    JOB_CANCELLED = "job_cancelled"


@dataclass(slots=True)
class SchedulerEvent:
    event_type: SchedulerEventType
    message: str
    job_id: str | None = None
