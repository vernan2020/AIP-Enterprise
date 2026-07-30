from __future__ import annotations

from dataclasses import dataclass, field
from threading import local
from typing import Any


@dataclass(slots=True)
class CorrelationContext:
    correlation_id: str | None = None
    execution_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _thread_local = local()

    @classmethod
    def set_current(cls, context: "CorrelationContext") -> None:
        cls._thread_local.value = context

    @classmethod
    def get_current(cls) -> "CorrelationContext | None":
        return getattr(cls._thread_local, "value", None)

    @classmethod
    def clear(cls) -> None:
        if hasattr(cls._thread_local, "value"):
            del cls._thread_local.value
