from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NotificationConfig:
    name: str = "notifications"
    max_retries: int = 3
    timeout_seconds: float = 5.0
    queue_size_limit: int = 100
