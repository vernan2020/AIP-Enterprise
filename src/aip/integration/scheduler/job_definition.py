from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aip.integration.contracts.connector import ConnectorProtocol, ConnectorType


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """Simple scheduler job definition used by the integration scheduler."""

    id: str
    connector: ConnectorProtocol | None = None
    connector_type: ConnectorType = ConnectorType.FUTURE
    connector_name: str = ""
    mode: str = "manual"
    scheduled: bool = False
    enabled: bool = True
    retries: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_connector_name(self) -> str:
        return self.connector_name or (
            self.connector.name if self.connector is not None else "unknown"
        )
