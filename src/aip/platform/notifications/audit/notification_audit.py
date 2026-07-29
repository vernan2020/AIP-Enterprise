from __future__ import annotations

from aip.platform.notifications.events.notification_events import NotificationEvent


class NotificationAudit:
    def __init__(self) -> None:
        self._entries: list[NotificationEvent] = []

    def record(self, event: NotificationEvent) -> None:
        self._entries.append(event)

    @property
    def entries(self) -> list[NotificationEvent]:
        return list(self._entries)
