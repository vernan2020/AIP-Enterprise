from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from aip.infrastructure.logging.manager import LoggingManager


class AuditService:
    def __init__(self, logging_manager: LoggingManager) -> None:
        self._logging = logging_manager

    def record(self, event: str, payload: dict[str, Any]) -> None:
        self._logging.bind(
            component="AUDIT",
            audit=True,
            audit_event=event,
            audit_payload=payload,
            audit_timestamp=datetime.now(timezone.utc).isoformat(),
        ).info(event)
