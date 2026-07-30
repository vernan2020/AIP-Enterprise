from __future__ import annotations

from threading import get_ident
from typing import Any

from aip.platform.observability.logging.structured_log import StructuredLog
from aip.platform.observability.providers.provider import LogProvider


class Logger:
    def __init__(self, *, provider: LogProvider | None = None) -> None:
        self.provider = provider

    def _emit(self, level: str, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, exception: Exception | None = None, metadata: dict[str, Any] | None = None) -> None:
        if self.provider is None:
            return
        payload = StructuredLog(
            level=level,
            message=message,
            correlation_id=correlation_id,
            execution_id=execution_id,
            component=component,
            thread=str(get_ident()),
            exception=str(exception) if exception is not None else None,
            metadata=metadata or {},
        )
        self.provider.emit(payload)

    def info(self, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._emit("INFO", message, correlation_id=correlation_id, execution_id=execution_id, component=component, metadata=metadata)

    def warning(self, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._emit("WARNING", message, correlation_id=correlation_id, execution_id=execution_id, component=component, metadata=metadata)

    def error(self, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, exception: Exception | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._emit("ERROR", message, correlation_id=correlation_id, execution_id=execution_id, component=component, exception=exception, metadata=metadata)

    def critical(self, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._emit("CRITICAL", message, correlation_id=correlation_id, execution_id=execution_id, component=component, metadata=metadata)

    def debug(self, message: str, *, correlation_id: str | None = None, execution_id: str | None = None, component: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._emit("DEBUG", message, correlation_id=correlation_id, execution_id=execution_id, component=component, metadata=metadata)
