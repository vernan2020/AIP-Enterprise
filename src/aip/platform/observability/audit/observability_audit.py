from __future__ import annotations

from aip.platform.observability.events.observability_events import ObservabilityEvent


class ObservabilityAudit:
    def __init__(self) -> None:
        self._entries: list[ObservabilityEvent] = []

    def record(self, event: ObservabilityEvent) -> None:
        self._entries.append(event)

    @property
    def entries(self) -> list[ObservabilityEvent]:
        return list(self._entries)
