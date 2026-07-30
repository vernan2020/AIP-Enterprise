from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, UTC
from threading import get_ident
from time import perf_counter
from typing import Any, Literal

from aip.platform.observability.tracing.trace_context import TraceContext


@dataclass(slots=True)
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    correlation_id: str | None = None
    execution_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, *, status: str = "completed") -> None:
        self.status = status
        self.ended_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float:
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()


class Tracer(AbstractContextManager):
    def __init__(self) -> None:
        self._active_span: Span | None = None

    def start_span(self, name: str, *, parent: Span | None = None, correlation_id: str | None = None, execution_id: str | None = None) -> "TracerSpanContext":
        trace_id = parent.trace_id if parent is not None else f"trace-{get_ident()}"
        span_id = f"span-{get_ident()}-{perf_counter():.6f}"
        span = Span(name=name, trace_id=trace_id, span_id=span_id, parent_span_id=parent.span_id if parent is not None else None, correlation_id=correlation_id, execution_id=execution_id)
        return TracerSpanContext(self, span)

    def __enter__(self) -> "Tracer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        return False


class TracerSpanContext(AbstractContextManager):
    def __init__(self, tracer: Tracer, span: Span) -> None:
        self._tracer = tracer
        self.span = span

    def __enter__(self) -> Span:
        self._tracer._active_span = self.span
        self.span.status = "active"
        return self.span

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        self.span.finish(status="completed")
        if self._tracer._active_span is self.span:
            self._tracer._active_span = None
        return False
