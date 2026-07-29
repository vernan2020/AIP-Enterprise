from __future__ import annotations


class NotificationHealthMonitor:
    def __init__(self) -> None:
        self._notifications_sent = 0
        self._failed_notifications = 0
        self._suppressed_notifications = 0
        self._deduplicated_notifications = 0
        self._provider_latency = 0.0
        self._queue_size = 0

    def record_sent(self, count: int = 1) -> None:
        self._notifications_sent += count

    def record_failed(self, count: int = 1) -> None:
        self._failed_notifications += count

    def record_suppressed(self, count: int = 1) -> None:
        self._suppressed_notifications += count

    def record_deduplicated(self, count: int = 1) -> None:
        self._deduplicated_notifications += count

    def record_latency(self, value: float) -> None:
        self._provider_latency = value

    def record_queue_size(self, size: int) -> None:
        self._queue_size = size

    def snapshot(self) -> dict[str, float | int]:
        return {
            "notifications_sent": self._notifications_sent,
            "failed_notifications": self._failed_notifications,
            "suppressed_notifications": self._suppressed_notifications,
            "deduplicated_notifications": self._deduplicated_notifications,
            "provider_latency": self._provider_latency,
            "queue_size": self._queue_size,
        }
