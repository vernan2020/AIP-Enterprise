from __future__ import annotations

from aip.platform.scheduler.events.scheduler_events import SchedulerEvent


class SchedulerAudit:
    def __init__(self) -> None:
        self._entries: list[SchedulerEvent] = []

    def record(self, event: SchedulerEvent) -> None:
        self._entries.append(event)

    @property
    def entries(self) -> list[SchedulerEvent]:
        return list(self._entries)
