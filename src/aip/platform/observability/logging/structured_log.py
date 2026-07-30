from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class StructuredLog:
    level: str
    message: str
    correlation_id: str | None = None
    execution_id: str | None = None
    timestamp: datetime | None = None
    component: str | None = None
    thread: str | None = None
    exception: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = (self.timestamp or datetime.now(UTC)).isoformat()
        return payload
