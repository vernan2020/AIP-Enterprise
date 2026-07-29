from __future__ import annotations

from datetime import datetime


class IntervalTrigger:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds

    def should_fire(self, now: datetime, previous_fire_time: datetime | None) -> bool:
        if previous_fire_time is None:
            return True
        return (now - previous_fire_time).total_seconds() >= self.seconds
