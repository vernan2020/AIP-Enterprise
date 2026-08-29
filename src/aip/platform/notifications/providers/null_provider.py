from __future__ import annotations

from aip.platform.notifications.models.notification import Notification
from aip.platform.notifications.models.notification_result import (
    NotificationResult,
    NotificationStatus,
)
from aip.platform.notifications.providers.provider import Provider


class NullProvider(Provider):
    name = "null"

    def send(
        self,
        notification: Notification,
        *,
        timeout_seconds: float | None = None,
        cancellation_token: str | None = None,
    ) -> NotificationResult:
        return NotificationResult(
            notification_id=notification.notification_id,
            status=NotificationStatus.SENT,
            retries=0,
            provider=self.name,
            duration_seconds=0.0,
        )

    def health(self) -> bool:
        return True
