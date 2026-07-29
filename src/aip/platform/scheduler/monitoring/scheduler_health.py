from __future__ import annotations

from collections import Counter
from datetime import datetime


class SchedulerHealthMonitor:
    def __init__(self) -> None:
        self._running_jobs: set[str] = set()
        self._queued_jobs: set[str] = set()
        self._failed_jobs: Counter[str] = Counter()
        self._retry_count = 0
        self._durations: list[float] = []
        self._last_execution: dict[str, datetime] = {}
        self._uptime_seconds = 0.0

    def record_running(self, job_id: str) -> None:
        self._running_jobs.add(job_id)

    def record_queued(self, job_id: str) -> None:
        self._queued_jobs.add(job_id)

    def record_failed(self, job_id: str) -> None:
        self._failed_jobs[job_id] += 1

    def record_retry(self, job_id: str) -> None:
        self._retry_count += 1

    def record_duration(self, job_id: str, duration: float) -> None:
        self._durations.append(duration)

    def record_last_execution(self, job_id: str, when: datetime) -> None:
        self._last_execution[job_id] = when

    def record_uptime(self, uptime_seconds: float) -> None:
        self._uptime_seconds = uptime_seconds

    def snapshot(self) -> dict[str, object]:
        return {
            "running_jobs": len(self._running_jobs),
            "queued_jobs": len(self._queued_jobs),
            "failed_jobs": sum(self._failed_jobs.values()),
            "retry_count": self._retry_count,
            "average_duration": sum(self._durations) / len(self._durations) if self._durations else 0.0,
            "last_execution": self._last_execution,
            "uptime_seconds": self._uptime_seconds,
        }
