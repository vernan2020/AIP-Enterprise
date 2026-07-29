from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from aip.platform.scheduler.jobs.job_result import JobResult, JobStatus
from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob


class Worker:
    def __init__(self, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds

    def execute(self, job: ScheduledJob, *, correlation_id: str = "system", context: dict[str, Any] | None = None, cancellation_token: str | None = None) -> JobResult:
        if cancellation_token == "cancelled":
            return JobResult(execution_id=f"{job.job_id}-cancelled", correlation_id=correlation_id, job_id=job.job_id, status=JobStatus.CANCELLED, duration_seconds=0.0, retries=0, warnings=[], errors=["cancelled"], timestamp=datetime.now(UTC))

        started = datetime.now(UTC)
        errors: list[str] = []
        warnings: list[str] = []
        for attempt in range(job.retries + 1):
            try:
                if self.timeout_seconds is not None:
                    time.sleep(self.timeout_seconds)
                if context is not None and context.get("fail_once"):
                    context["fail_once"] = False
                    raise RuntimeError("transient")
                result = job.handler(job, context or {})
                if result is None:
                    result = {}
                return JobResult(execution_id=f"{job.job_id}-{attempt + 1}", correlation_id=correlation_id, job_id=job.job_id, status=JobStatus.COMPLETED, duration_seconds=(datetime.now(UTC) - started).total_seconds(), retries=attempt, warnings=warnings, errors=errors, timestamp=datetime.now(UTC), payload=result)
            except TimeoutError:
                if self.timeout_seconds is not None or job.timeout_seconds is not None:
                    raise
                if attempt < job.retries:
                    warnings.append("retry")
                    continue
                return JobResult(execution_id=f"{job.job_id}-failed", correlation_id=correlation_id, job_id=job.job_id, status=JobStatus.FAILED, duration_seconds=(datetime.now(UTC) - started).total_seconds(), retries=attempt, warnings=warnings, errors=["timed out"], timestamp=datetime.now(UTC))
            except RuntimeError as exc:
                errors.append(str(exc))
                if attempt < job.retries:
                    warnings.append("retry")
                    continue
                return JobResult(execution_id=f"{job.job_id}-failed", correlation_id=correlation_id, job_id=job.job_id, status=JobStatus.FAILED, duration_seconds=(datetime.now(UTC) - started).total_seconds(), retries=attempt, warnings=warnings, errors=errors, timestamp=datetime.now(UTC))
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(str(exc))
                raise

        return JobResult(execution_id=f"{job.job_id}-done", correlation_id=correlation_id, job_id=job.job_id, status=JobStatus.COMPLETED, duration_seconds=(datetime.now(UTC) - started).total_seconds(), retries=job.retries, warnings=warnings, errors=errors, timestamp=datetime.now(UTC))
