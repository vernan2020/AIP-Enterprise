from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class SystemStatus:
    """Application-wide system status snapshot."""

    execution_mode: str
    environment: str
    source_states: dict[str, str] = field(default_factory=dict)
    last_refresh: datetime | None = None
    component_details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "environment": self.environment,
            "source_states": dict(self.source_states),
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "component_details": dict(self.component_details),
        }
