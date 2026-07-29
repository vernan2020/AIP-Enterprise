from __future__ import annotations

from datetime import datetime


class CronTrigger:
    def __init__(self, expression: str) -> None:
        self.expression = expression

    def should_fire(self, now: datetime, previous_fire_time: datetime | None) -> bool:
        return previous_fire_time is None or now >= previous_fire_time
