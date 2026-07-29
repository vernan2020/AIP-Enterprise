from __future__ import annotations

from aip.platform.scheduler.jobs.job_priority import JobPriority
from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}

    def register(self, job: ScheduledJob) -> None:
        self._jobs[job.job_id] = job

    def unregister(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    def lookup(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def by_priority(self, priority: JobPriority) -> list[ScheduledJob]:
        return [job for job in self._jobs.values() if job.priority == priority]

    def dependency_graph(self, job_id: str) -> list[str]:
        job = self.lookup(job_id)
        return list(job.dependencies) if job is not None else []

    def is_enabled(self, job_id: str) -> bool:
        job = self.lookup(job_id)
        return bool(job and job.enabled)

    def disable(self, job_id: str) -> None:
        job = self.lookup(job_id)
        if job is not None:
            job.disable()

    def enable(self, job_id: str) -> None:
        job = self.lookup(job_id)
        if job is not None:
            job.enable()
