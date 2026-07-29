from __future__ import annotations

from datetime import datetime


class ManualTrigger:
    def should_fire(self, now: datetime, previous_fire_time: datetime | None) -> bool:
        return True
