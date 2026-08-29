from __future__ import annotations

from typing import Protocol

from aip.platform.notifications.models.notification import Notification
from aip.platform.notifications.models.notification_result import NotificationResult


class Provider(Protocol):
    name: str

    def send(
        self,
        notification: Notification,
        *,
        timeout_seconds: float | None = None,
        cancellation_token: str | None = None,
    ) -> NotificationResult: ...

    def health(self) -> bool: ...
