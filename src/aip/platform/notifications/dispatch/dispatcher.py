from __future__ import annotations

from datetime import UTC, datetime

from aip.platform.notifications.exceptions.notification_exceptions import NotificationError
from aip.platform.notifications.models.notification import Notification
from aip.platform.notifications.models.notification_result import (
    NotificationResult,
    NotificationStatus,
)
from aip.platform.notifications.providers.provider import Provider


class Dispatcher:
    def __init__(self, *, provider: Provider, max_retries: int = 0) -> None:
        self.provider = provider
        self.max_retries = max_retries

    def dispatch(
        self,
        notification: Notification,
        *,
        timeout_seconds: float | None = None,
        cancellation_token: str | None = None,
    ) -> NotificationResult:
        if cancellation_token == "cancelled":
            return NotificationResult(
                notification_id=notification.notification_id,
                status=NotificationStatus.CANCELLED,
                retries=0,
                provider=self.provider.name,
                timestamp=datetime.now(UTC),
                duration_seconds=0.0,
            )

        for attempt in range(self.max_retries + 1):
            try:
                result = self.provider.send(
                    notification,
                    timeout_seconds=timeout_seconds,
                    cancellation_token=cancellation_token,
                )
                return NotificationResult(
                    notification_id=notification.notification_id,
                    status=result.status,
                    retries=attempt,
                    provider=self.provider.name,
                    timestamp=datetime.now(UTC),
                    duration_seconds=0.0,
                )
            except TimeoutError:
                if attempt < self.max_retries:
                    continue
                raise
            except Exception as exc:  # pragma: no cover - defensive
                raise NotificationError(f"notification failed: {exc}") from exc

        raise NotificationError("notification failed")
