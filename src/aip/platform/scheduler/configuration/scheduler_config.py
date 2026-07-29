from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchedulerConfig:
    name: str = "scheduler"
    poll_interval_seconds: int = 30
    shutdown_timeout_seconds: int = 5
    max_parallel_jobs: int = 4
