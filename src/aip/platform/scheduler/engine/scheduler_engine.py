from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, RLock
from typing import Any

from aip.platform.scheduler.audit.scheduler_audit import SchedulerAudit
from aip.platform.scheduler.configuration.scheduler_config import SchedulerConfig
from aip.platform.scheduler.engine.execution_engine import ExecutionEngine
from aip.platform.scheduler.events.scheduler_events import SchedulerEvent, SchedulerEventType
from aip.platform.scheduler.exceptions.scheduler_exceptions import SchedulerError
from aip.platform.scheduler.jobs.job_result import JobStatus
from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob
from aip.platform.scheduler.locking.execution_lock import ExecutionLock
from aip.platform.scheduler.monitoring.scheduler_health import SchedulerHealthMonitor
from aip.platform.scheduler.queue.execution_queue import ExecutionQueue
from aip.platform.scheduler.queue.worker import Worker
from aip.platform.scheduler.registry.job_registry import JobRegistry
from aip.platform.scheduler.telemetry.scheduler_metrics import SchedulerMetrics


class SchedulerEngine:
    def __init__(
        self,
        *,
        config: SchedulerConfig,
        registry: JobRegistry,
        queue: ExecutionQueue | None = None,
        worker: Worker | None = None,
        lock: ExecutionLock | None = None,
        metrics: SchedulerMetrics | None = None,
        health: SchedulerHealthMonitor | None = None,
        audit: SchedulerAudit | None = None,
        execution_engine: ExecutionEngine | None = None,
    ) -> None:
        self.config = config
        self.registry = registry
        self.queue = queue or ExecutionQueue()
        self.worker = worker or Worker()
        self.lock = lock or ExecutionLock()
        self.metrics = metrics or SchedulerMetrics()
        self.health = health or SchedulerHealthMonitor()
        self.audit = audit or SchedulerAudit()
        self.execution_engine = execution_engine or ExecutionEngine(
            registry=registry,
            worker=self.worker,
            lock=self.lock,
            metrics=self.metrics,
            health=self.health,
        )
        self._started = False
        self._stopped = Event()
        self._state_lock = RLock()

    def start(self) -> None:
        with self._state_lock:
            self._started = True
            self._stopped.clear()
            self.health.record_uptime(0.0)
            self.audit.record(SchedulerEvent(event_type=SchedulerEventType.SCHEDULER_STARTED, message="scheduler started"))

    def shutdown(self) -> None:
        with self._state_lock:
            if not self._started:
                raise SchedulerError("scheduler stopped")
            self._started = False
            self._stopped.set()
            self.audit.record(SchedulerEvent(event_type=SchedulerEventType.SCHEDULER_STOPPED, message="scheduler stopped"))

    def execute_job(self, job_id: str, *, context: dict[str, Any] | None = None) -> Any:
        with self._state_lock:
            if not self._started and self._stopped.is_set():
                raise SchedulerError("scheduler stopped")
            job = self.registry.lookup(job_id)
            if job is None:
                raise SchedulerError(f"job not found: {job_id}")
            return self.execution_engine.execute(job, context=context or {})
