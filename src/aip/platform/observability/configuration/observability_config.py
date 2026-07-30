from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.platform.observability.exceptions.observability_exceptions import ObservabilityError


@dataclass(slots=True)
class ObservabilityConfig:
    service_name: str = "aip"
    enabled: bool = True
    json_logs: bool = False
    log_level: str = "INFO"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "ObservabilityConfig":
        return cls(**values)

    def validate(self) -> None:
        if not self.service_name.strip():
            raise ObservabilityError("service name is required")
