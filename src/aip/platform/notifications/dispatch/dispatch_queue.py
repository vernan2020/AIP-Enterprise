from __future__ import annotations

from collections import deque

from aip.platform.notifications.models.notification import Notification


class DispatchQueue:
    def __init__(self) -> None:
        self._queue: deque[Notification] = deque()

    def enqueue(self, notification: Notification) -> None:
        self._queue.append(notification)

    def dequeue(self) -> Notification | None:
        return self._queue.popleft() if self._queue else None

    def size(self) -> int:
        return len(self._queue)
