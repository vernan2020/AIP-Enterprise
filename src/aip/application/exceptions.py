from __future__ import annotations


class ApplicationError(RuntimeError):
    """Base class for application-layer failures."""


class WorkflowError(ApplicationError):
    """Raised when an application workflow cannot complete successfully."""


class OrchestrationError(ApplicationError):
    """Raised when an application orchestrator cannot complete successfully."""


class ContractValidationError(ApplicationError):
    """Raised when application contracts are invalid."""


class EventDispatchError(ApplicationError):
    """Raised when event dispatching fails."""


class TelemetryError(ApplicationError):
    """Raised when telemetry cannot be recorded."""


class WorkflowExecutionError(WorkflowError):
    """Raised when an application workflow cannot complete successfully."""


class OrchestratorExecutionError(OrchestrationError):
    """Raised when an application orchestrator cannot complete successfully."""


def translate_application_exception(exc: Exception, *, context: str = "workflow") -> ApplicationError:
    if isinstance(exc, ApplicationError):
        return exc
    if context == "orchestrator":
        return OrchestratorExecutionError(f"{context} failed: {exc}")
    if isinstance(exc, (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError)):
        return ContractValidationError(f"{context} failed: {exc}")
    return WorkflowExecutionError(f"{context} failed: {exc}")
