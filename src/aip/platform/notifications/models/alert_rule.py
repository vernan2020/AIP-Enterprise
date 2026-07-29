from __future__ import annotations

from dataclasses import dataclass

from aip.platform.notifications.severity.severity import Severity


@dataclass(slots=True)
class AlertRule:
    rule_id: str
    name: str
    severity: Severity
    threshold: int = 1
    event_type: str | None = None
