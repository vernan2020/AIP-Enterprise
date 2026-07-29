from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import pytest

from aip.platform.scheduler.audit.scheduler_audit import SchedulerAudit
from aip.platform.scheduler.configuration.scheduler_config import SchedulerConfig
from aip.platform.scheduler.engine.execution_engine import ExecutionEngine
from aip.platform.scheduler.engine.scheduler_engine import SchedulerEngine
from aip.platform.scheduler.events.scheduler_events import SchedulerEvent, SchedulerEventType
from aip.platform.scheduler.exceptions.scheduler_exceptions import SchedulerError
from aip.platform.scheduler.jobs.job_history import JobHistory
from aip.platform.scheduler.jobs.job_priority import JobPriority
from aip.platform.scheduler.jobs.job_result import JobResult, JobStatus
from aip.platform.scheduler.jobs.scheduled_job import ScheduledJob
from aip.platform.scheduler.locking.execution_lock import ExecutionLock
from aip.platform.scheduler.monitoring.scheduler_health import SchedulerHealthMonitor
from aip.platform.scheduler.queue.execution_queue import ExecutionQueue
from aip.platform.scheduler.queue.worker import Worker
from aip.platform.scheduler.registry.job_registry import JobRegistry
from aip.platform.scheduler.telemetry.scheduler_metrics import SchedulerMetrics
from aip.platform.scheduler.triggers.cron_trigger import CronTrigger
from aip.platform.scheduler.triggers.interval_trigger import IntervalTrigger
from aip.platform.scheduler.triggers.manual_trigger import ManualTrigger
from aip.platform.scheduler.triggers.startup_trigger import StartupTrigger


@dataclass
class RecordingHandler:
    calls: list[str] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def __call__(self, job: ScheduledJob, context: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.calls.append(job.job_id)
        return {"job_id": job.job_id}


def test_registry_supports_registration_lookup_priority_and_dependency_graph() -> None:
    registry = JobRegistry()
    parent = ScheduledJob(job_id="parent", name="parent", handler=lambda job, context: {}, trigger=ManualTrigger(), priority=JobPriority.HIGH)
    child = ScheduledJob(job_id="child", name="child", handler=lambda job, context: {}, trigger=ManualTrigger(), priority=JobPriority.NORMAL, dependencies=["parent"])

    registry.register(parent)
    registry.register(child)

    assert registry.lookup("parent") is parent
    assert registry.lookup("missing") is None
    assert registry.by_priority(JobPriority.HIGH)[0].job_id == "parent"
    assert registry.is_enabled("parent") is True
    assert registry.dependency_graph("child") == ["parent"]

    registry.disable("child")
    assert registry.is_enabled("child") is False

    registry.unregister("child")
    assert registry.lookup("child") is None


def test_triggers_support_cron_interval_manual_and_startup() -> None:
    cron = CronTrigger("0 * * * *")
    interval = IntervalTrigger(seconds=60)
    manual = ManualTrigger()
    startup = StartupTrigger()

    now = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    assert cron.should_fire(now, now - timedelta(hours=1)) is True
    assert interval.should_fire(now, now - timedelta(minutes=30)) is True
    assert manual.should_fire(now, now) is True
    assert startup.should_fire(now, None) is True


def test_execution_queue_and_worker_handle_success_retry_timeout_and_cancellation() -> None:
    queue = ExecutionQueue()
    job = ScheduledJob(job_id="job-1", name="job-1", handler=lambda job, context: {"ok": True}, trigger=ManualTrigger())
    queue.enqueue(job)
    assert queue.dequeue() is job
    assert queue.size() == 0

    worker = Worker(timeout_seconds=0.05)
    completed = worker.execute(job, correlation_id="corr")
    assert completed.status == JobStatus.COMPLETED

    flaky = ScheduledJob(job_id="job-2", name="job-2", handler=lambda job, context: (_ for _ in ()).throw(TimeoutError("slow")), trigger=ManualTrigger(), retries=1)
    cancelled = worker.execute(flaky, cancellation_token="cancelled")
    assert cancelled.status == JobStatus.CANCELLED

    with pytest.raises(TimeoutError):
        worker.execute(ScheduledJob(job_id="job-3", name="job-3", handler=lambda job, context: (_ for _ in ()).throw(TimeoutError("slow")), trigger=ManualTrigger(), timeout_seconds=0.01))


def test_locking_supports_single_instance_job_lock_and_forced_unlock() -> None:
    lock = ExecutionLock()
    assert lock.acquire("scheduler") is True
    assert lock.acquire("scheduler") is False
    assert lock.release("scheduler") is True
    assert lock.force_unlock("scheduler") is True
    assert lock.acquire("job-1") is True
    assert lock.release("job-1") is True


def test_history_and_audit_record_results_and_events() -> None:
    history = JobHistory()
    result = JobResult(execution_id="exec-1", correlation_id="corr-1", job_id="job-a", status=JobStatus.COMPLETED, duration_seconds=1.2, retries=0, warnings=["warn"], errors=[], timestamp=datetime.now(UTC))
    history.record(result)
    assert history.latest().execution_id == "exec-1"

    audit = SchedulerAudit()
    event = SchedulerEvent(event_type=SchedulerEventType.JOB_STARTED, message="job started", job_id="job-a")
    audit.record(event)
    assert audit.entries[-1].job_id == "job-a"


def test_metrics_and_health_monitor_track_runtime_state() -> None:
    metrics = SchedulerMetrics()
    metrics.increment("executions")
    metrics.gauge("queue_depth", 3)
    assert metrics.snapshot()["executions"] == 1

    health = SchedulerHealthMonitor()
    health.record_running("job-a")
    health.record_queued("job-b")
    health.record_failed("job-c")
    health.record_retry("job-a")
    health.record_duration("job-a", 1.5)
    health.record_last_execution("job-a", datetime.now(UTC))
    health.record_uptime(12.0)

    snapshot = health.snapshot()
    assert snapshot["running_jobs"] == 1
    assert snapshot["queued_jobs"] == 1
    assert snapshot["failed_jobs"] == 1
    assert snapshot["retry_count"] == 1
    assert snapshot["average_duration"] >= 0.0


def test_execution_engine_resolves_dependencies_and_runs_parallel_jobs() -> None:
    registry = JobRegistry()
    handler = RecordingHandler()
    parent = ScheduledJob(job_id="parent", name="parent", handler=handler, trigger=ManualTrigger())
    child = ScheduledJob(job_id="child", name="child", handler=handler, trigger=ManualTrigger(), dependencies=["parent"])
    registry.register(parent)
    registry.register(child)

    engine = ExecutionEngine(registry=registry, worker=Worker(), lock=ExecutionLock(), metrics=SchedulerMetrics(), health=SchedulerHealthMonitor())
    results = engine.execute_many([child], parallel=False)
    assert results[0].status == JobStatus.COMPLETED
    assert handler.calls == ["parent", "child"]

    registry2 = JobRegistry()
    a = ScheduledJob(job_id="a", name="a", handler=lambda job, context: {"ok": True}, trigger=ManualTrigger())
    b = ScheduledJob(job_id="b", name="b", handler=lambda job, context: {"ok": True}, trigger=ManualTrigger())
    registry2.register(a)
    registry2.register(b)
    engine2 = ExecutionEngine(registry=registry2, worker=Worker(), lock=ExecutionLock(), metrics=SchedulerMetrics(), health=SchedulerHealthMonitor())
    results2 = engine2.execute_many([a, b], parallel=True)
    assert len(results2) == 2
    assert {result.job_id for result in results2} == {"a", "b"}


def test_scheduler_engine_supports_graceful_shutdown_and_event_publishing() -> None:
    config = SchedulerConfig(name="demo", poll_interval_seconds=1)
    registry = JobRegistry()
    job = ScheduledJob(job_id="job-x", name="job-x", handler=lambda job, context: {"ok": True}, trigger=ManualTrigger())
    registry.register(job)
    engine = SchedulerEngine(config=config, registry=registry, queue=ExecutionQueue(), worker=Worker(), lock=ExecutionLock(), metrics=SchedulerMetrics(), health=SchedulerHealthMonitor(), audit=SchedulerAudit())

    engine.start()
    engine.shutdown()

    with pytest.raises(SchedulerError, match="stopped"):
        engine.execute_job(job.job_id)


def test_scheduler_engine_retries_and_reports_failure() -> None:
    registry = JobRegistry()

    def flaky(job: ScheduledJob, context: dict[str, Any]) -> dict[str, Any]:
        context["attempts"] = context.get("attempts", 0) + 1
        if context["attempts"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    job = ScheduledJob(job_id="job-r", name="job-r", handler=flaky, trigger=ManualTrigger(), retries=2)
    registry.register(job)
    engine = SchedulerEngine(config=SchedulerConfig(name="retry", poll_interval_seconds=1), registry=registry, queue=ExecutionQueue(), worker=Worker(), lock=ExecutionLock(), metrics=SchedulerMetrics(), health=SchedulerHealthMonitor(), audit=SchedulerAudit())

    result = engine.execute_job(job.job_id, context={"attempts": 0})
    assert result.status == JobStatus.COMPLETED
    assert result.retries == 2


def test_scheduler_edge_paths_cover_disabled_locked_and_dependency_paths() -> None:
    registry = JobRegistry()
    parent = ScheduledJob(job_id="parent", name="parent", handler=lambda job, context: {}, trigger=ManualTrigger())
    child = ScheduledJob(job_id="child", name="child", handler=lambda job, context: {}, trigger=ManualTrigger(), dependencies=["parent"])
    registry.register(parent)
    registry.register(child)
    registry.disable("child")

    lock = ExecutionLock()
    engine = ExecutionEngine(registry=registry, worker=Worker(), lock=lock, metrics=SchedulerMetrics(), health=SchedulerHealthMonitor())
    skipped = engine.execute(child)
    assert skipped.status == JobStatus.SKIPPED

    registry.enable("child")
    assert lock.acquire("child") is True
    locked = engine.execute(child)
    assert locked.status == JobStatus.CANCELLED

    results = engine.execute_many([child, parent])
    assert results[0].job_id == "parent"
    assert results[1].job_id == "child"

    with pytest.raises(SchedulerError, match="scheduler stopped"):
        stopped_engine = SchedulerEngine(config=SchedulerConfig(name="stopped"), registry=registry, queue=ExecutionQueue(), worker=Worker(), lock=ExecutionLock(), metrics=SchedulerMetrics(), health=SchedulerHealthMonitor(), audit=SchedulerAudit())
        stopped_engine.shutdown()


def test_worker_and_history_cover_retry_and_state_paths() -> None:
    worker = Worker()

    def fail_once(job: ScheduledJob, context: dict[str, Any]) -> dict[str, Any]:
        if context.get("attempts", 0) == 0:
            context["attempts"] = 1
            raise RuntimeError("transient")
        return {"ok": True}

    result = worker.execute(ScheduledJob(job_id="retry", name="retry", handler=fail_once, trigger=ManualTrigger(), retries=1), context={"attempts": 0})
    assert result.status == JobStatus.COMPLETED
    assert result.retries == 1

    def timeout_once(job: ScheduledJob, context: dict[str, Any]) -> dict[str, Any]:
        raise TimeoutError("slow")

    failed = worker.execute(ScheduledJob(job_id="timeout", name="timeout", handler=timeout_once, trigger=ManualTrigger(), retries=1), context={})
    assert failed.status == JobStatus.FAILED

    history = JobHistory()
    history.record(JobResult(execution_id="exec-2", correlation_id="corr-2", job_id="job-b", status=JobStatus.COMPLETED, duration_seconds=0.5, retries=0, warnings=[], errors=[], timestamp=datetime.now(UTC)))
    assert history.entries[-1].job_id == "job-b"

    job = ScheduledJob(job_id="job-z", name="job-z", handler=lambda job, context: {}, trigger=ManualTrigger())
    job.disable()
    job.enable()
    assert job.enabled is True

    registry = JobRegistry()
    registry.disable("missing")
    registry.enable("missing")

    trigger = IntervalTrigger(seconds=60)
    assert trigger.should_fire(datetime.now(UTC), None) is True

    lock = ExecutionLock()
    assert lock.release("missing") is False
    assert lock.force_unlock("missing") is True
