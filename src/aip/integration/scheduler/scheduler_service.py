from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from aip.core.exceptions import InfrastructureError
from aip.integration.audit.execution_result import ExecutionResult, ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorProtocol
from aip.integration.contracts.synchronization import (
    SynchronizationJob,
    SynchronizationRequest,
    SynchronizationScheduler,
)
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.scheduler.job_definition import JobDefinition


@dataclass(slots=True)
class SchedulerService(SynchronizationScheduler):
    """Infrastructure scheduler supporting manual, scheduled, retry, and cancellation flows."""

    connectors: dict[str, ConnectorProtocol] = field(default_factory=dict)
    event_bus: IntegrationEventBus | None = None
    _history: list[ExecutionResult] = field(default_factory=list, init=False)
    _statuses: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _jobs: dict[str, JobDefinition] = field(default_factory=dict, init=False)
    _retry_attempts: dict[str, int] = field(default_factory=dict, init=False)
    _scheduled: dict[str, datetime] = field(default_factory=dict, init=False)

    def register_connector(self, connector: ConnectorProtocol) -> None:
        self.connectors[connector.name] = connector

    def run_job(self, job: JobDefinition) -> ExecutionResult:
        self._jobs[job.id] = job
        self._retry_attempts[job.id] = self._retry_attempts.get(job.id, 0)
        return self._execute(job)

    def retry_job(self, job_id: str) -> ExecutionResult:
        job = self._jobs.get(job_id)
        if job is None:
            raise IntegrationError(f"Job '{job_id}' is not registered")
        self._retry_attempts[job_id] = self._retry_attempts.get(job_id, 0) + 1
        return self._execute(job, is_retry=True)

    def schedule_job(self, job: JobDefinition, *, scheduled_for: datetime | None = None) -> None:
        self._jobs[job.id] = job
        self._scheduled[job.id] = scheduled_for or datetime.now(UTC) + timedelta(minutes=1)
        self._statuses[job.id] = {"status": ExecutionStatus.PENDING.value, "job_id": job.id}

    def cancel_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        job = self._jobs[job_id]
        connector_name = job.connector_name or (
            job.connector.name if job.connector is not None else "unknown"
        )
        self._statuses[job_id] = {
            "status": ExecutionStatus.CANCELLED.value,
            "job_id": job_id,
        }
        cancelled_result = ExecutionResult(
            execution_id=job_id,
            correlation_id=job_id,
            connector=connector_name,
            duration_seconds=0.0,
            records_processed=0,
            warnings=[],
            errors=[],
            user="system",
            timestamp=datetime.now(UTC),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status=ExecutionStatus.CANCELLED,
        )
        self._history.append(cancelled_result)
        self._publish(SynchronizationEvent.cancelled(job_id, connector_name, job_id))
        return True

    def get_status(self, job_id: str) -> ExecutionStatus:
        status = self._statuses.get(job_id, {}).get("status", ExecutionStatus.PENDING.value)
        return ExecutionStatus(status)

    def get_history(self, job_id: str | None = None) -> list[ExecutionResult]:
        if job_id is None:
            return list(self._history)
        return [result for result in self._history if result.correlation_id == job_id]

    def execute(self, job: SynchronizationJob) -> ExecutionResult:
        return self.run_job(
            JobDefinition(
                id=job.id,
                connector_name=job.connector_name,
            )
        )

    def cancel(self, job_id: str) -> bool:
        return self.cancel_job(job_id)

    def status(self, job_id: str) -> dict[str, Any]:
        return dict(
            self._statuses.get(job_id, {"status": ExecutionStatus.PENDING.value, "job_id": job_id})
        )

    def history(self, connector_name: str | None = None) -> list[dict[str, Any]]:
        items = [result.to_dict() for result in self._history]
        if connector_name is None:
            return items
        return [item for item in items if item.get("connector") == connector_name]

    def _execute(self, job: JobDefinition, *, is_retry: bool = False) -> ExecutionResult:
        connector = job.connector
        if connector is None:
            connector = self.connectors.get(job.resolved_connector_name())
        if connector is None:
            raise IntegrationError(f"Connector '{job.resolved_connector_name()}' is not registered")

        execution_id = f"{job.id}-{len(self._history) + 1}"
        started_at = datetime.now(UTC)
        self._statuses[job.id] = {
            "status": ExecutionStatus.RUNNING.value,
            "job_id": job.id,
            "execution_id": execution_id,
        }
        self._publish(SynchronizationEvent.started(job.id, connector.name, execution_id))

        try:
            connector.connect()
            if not connector.health():
                raise IntegrationError("Connector is not available")
            request = SynchronizationRequest(
                connector_name=connector.name,
                correlation_id=job.id,
                user="system",
                records_expected=1,
            )
            validation = connector.validate({"connector": connector.name, "job_id": job.id})
            if not validation.ok:
                raise InfrastructureError("Validation failed")
            connector.normalize({"connector": connector.name, "job_id": job.id})
            records_processed = connector.synchronize(request)
            result = ExecutionResult(
                execution_id=execution_id,
                correlation_id=job.id,
                connector=connector.name,
                duration_seconds=0.0,
                records_processed=records_processed,
                warnings=[],
                errors=[],
                user="system",
                timestamp=datetime.now(UTC),
                started_at=started_at,
                finished_at=datetime.now(UTC),
                status=ExecutionStatus.COMPLETED,
            )
            self._history.append(result)
            self._statuses[job.id] = {
                "status": ExecutionStatus.COMPLETED.value,
                "job_id": job.id,
                "execution_id": execution_id,
            }
            self._retry_attempts[job.id] = 0
            connector.audit(
                SynchronizationLog(
                    execution_id=execution_id,
                    correlation_id=job.id,
                    connector=connector.name,
                    duration_seconds=0.0,
                    records_processed=records_processed,
                    warnings=[],
                    errors=[],
                    user="system",
                    timestamp=datetime.now(UTC),
                )
            )
            self._publish(
                SynchronizationEvent.completed(job.id, connector.name, execution_id, result)
            )
            return result
        except Exception as exc:  # noqa: BLE001
            finished_at = datetime.now(UTC)
            failed_result = ExecutionResult(
                execution_id=execution_id,
                correlation_id=job.id,
                connector=connector.name,
                duration_seconds=0.0,
                records_processed=0,
                warnings=[],
                errors=[str(exc)],
                user="system",
                timestamp=finished_at,
                started_at=started_at,
                finished_at=finished_at,
                status=ExecutionStatus.FAILED,
            )
            self._history.append(failed_result)
            self._statuses[job.id] = {
                "status": ExecutionStatus.FAILED.value,
                "job_id": job.id,
                "execution_id": execution_id,
                "error": str(exc),
            }
            if is_retry and self._retry_attempts.get(job.id, 0) > 1:
                self._publish(
                    SynchronizationEvent.retry(
                        job.id, connector.name, execution_id, self._retry_attempts[job.id]
                    )
                )
            self._publish(
                SynchronizationEvent.failed(job.id, connector.name, execution_id, str(exc))
            )
            return failed_result
        finally:
            connector.disconnect()

    def _publish(self, event: SynchronizationEvent) -> None:
        if self.event_bus is not None:
            self.event_bus.publish(event)
