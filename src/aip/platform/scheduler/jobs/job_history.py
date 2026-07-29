from __future__ import annotations

from aip.platform.scheduler.jobs.job_result import JobResult


class JobHistory:
    def __init__(self) -> None:
        self._records: list[JobResult] = []

    def record(self, result: JobResult) -> None:
        self._records.append(result)

    def latest(self) -> JobResult | None:
        return self._records[-1] if self._records else None

    @property
    def entries(self) -> list[JobResult]:
        return list(self._records)
