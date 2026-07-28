from __future__ import annotations

from enum import Enum

from aip.application.exceptions import WorkflowExecutionError


class WorkflowLifecycleState(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class BaseWorkflow:
    """Simple lifecycle support for application workflows."""

    def __init__(self) -> None:
        self._lifecycle_state = WorkflowLifecycleState.CREATED

    @property
    def lifecycle_state(self) -> WorkflowLifecycleState:
        return self._lifecycle_state

    def begin_execution(self) -> None:
        if self._lifecycle_state in {WorkflowLifecycleState.RUNNING}:
            raise WorkflowExecutionError("workflow is already running")
        self._lifecycle_state = WorkflowLifecycleState.RUNNING

    def complete_execution(self) -> None:
        if self._lifecycle_state != WorkflowLifecycleState.RUNNING:
            raise WorkflowExecutionError("workflow must be running before completion")
        self._lifecycle_state = WorkflowLifecycleState.COMPLETED

    def mark_partially_completed(self) -> None:
        if self._lifecycle_state != WorkflowLifecycleState.RUNNING:
            raise WorkflowExecutionError("workflow must be running before partial completion")
        self._lifecycle_state = WorkflowLifecycleState.PARTIALLY_COMPLETED

    def fail_execution(self) -> None:
        if self._lifecycle_state != WorkflowLifecycleState.RUNNING:
            raise WorkflowExecutionError("workflow must be running before failure")
        self._lifecycle_state = WorkflowLifecycleState.FAILED
