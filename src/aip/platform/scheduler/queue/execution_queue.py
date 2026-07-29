from __future__ import annotations

from collections import deque

from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob


class ExecutionQueue:
    def __init__(self) -> None:
        self._queue: deque[ScheduledJob] = deque()

    def enqueue(self, job: ScheduledJob) -> None:
        self._queue.append(job)

    def dequeue(self) -> ScheduledJob | None:
        return self._queue.popleft() if self._queue else None

    def size(self) -> int:
        return len(self._queue)
