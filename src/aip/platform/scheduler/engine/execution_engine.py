from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from aip.platform.scheduler.exceptions.scheduler_exceptions import SchedulerError
from aip.platform.scheduler.jobs.job_result import JobResult, JobStatus
from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob
from aip.platform.scheduler.locking.execution_lock import ExecutionLock
from aip.platform.scheduler.monitoring.scheduler_health import SchedulerHealthMonitor
from aip.platform.scheduler.queue.execution_queue import ExecutionQueue
from aip.platform.scheduler.queue.worker import Worker
from aip.platform.scheduler.registry.job_registry import JobRegistry
from aip.platform.scheduler.telemetry.scheduler_metrics import SchedulerMetrics


class ExecutionEngine:
    def __init__(
        self,
        *,
        registry: JobRegistry,
        worker: Worker | None = None,
        lock: ExecutionLock | None = None,
        metrics: SchedulerMetrics | None = None,
        health: SchedulerHealthMonitor | None = None,
        queue: ExecutionQueue | None = None,
    ) -> None:
        self.registry = registry
        self.worker = worker or Worker()
        self.lock = lock or ExecutionLock()
        self.metrics = metrics or SchedulerMetrics()
        self.health = health or SchedulerHealthMonitor()
        self.queue = queue or ExecutionQueue()

    def execute(self, job: ScheduledJob, *, context: dict[str, Any] | None = None) -> JobResult:
        if not self.registry.is_enabled(job.job_id):
            return JobResult(execution_id=f"{job.job_id}-disabled", correlation_id="system", job_id=job.job_id, status=JobStatus.SKIPPED, duration_seconds=0.0, retries=0, warnings=[], errors=["disabled"], timestamp=datetime.now(UTC))

        if not self.lock.acquire(job.job_id):
            return JobResult(execution_id=f"{job.job_id}-locked", correlation_id="system", job_id=job.job_id, status=JobStatus.CANCELLED, duration_seconds=0.0, retries=0, warnings=["locked"], errors=[], timestamp=datetime.now(UTC))

        try:
            self.health.record_running(job.job_id)
            self.queue.enqueue(job)
            result = self.worker.execute(job, correlation_id="system", context=context or {})
            self.health.record_last_execution(job.job_id, datetime.now(UTC))
            self.metrics.increment("executions")
            return result
        finally:
            self.lock.release(job.job_id)

    def execute_many(self, jobs: list[ScheduledJob], *, parallel: bool = False, context: dict[str, Any] | None = None) -> list[JobResult]:
        resolved_jobs = self._resolve_dependencies(jobs)
        if not parallel:
            return [self.execute(job, context=context) for job in resolved_jobs]

        with ThreadPoolExecutor(max_workers=max(2, len(resolved_jobs))) as pool:
            futures = [pool.submit(self.execute, job, context=context) for job in resolved_jobs]
            return [future.result() for future in futures]

    def _resolve_dependencies(self, jobs: list[ScheduledJob]) -> list[ScheduledJob]:
        resolved: list[ScheduledJob] = []
        visited: set[str] = set()

        def visit(job: ScheduledJob) -> None:
            if job.job_id in visited:
                return
            for dependency_id in job.dependencies:
                dependency = self.registry.lookup(dependency_id)
                if dependency is not None:
                    visit(dependency)
            if job not in resolved:
                resolved.append(job)
                visited.add(job.job_id)

        for job in jobs:
            visit(job)

        return resolved
