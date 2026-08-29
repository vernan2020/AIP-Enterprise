from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SQLHealthMonitor:
    """Tracks SQL connector health and execution characteristics."""

    _states: dict[str, dict[str, Any]] = field(default_factory=dict)

    def record_connection(
        self, connector_name: str, *, healthy: bool, latency_ms: float, retries: int
    ) -> None:
        self._states[connector_name] = {
            "healthy": healthy,
            "latency_ms": latency_ms,
            "retries": retries,
            "failures": self._states.get(connector_name, {}).get("failures", 0),
        }

    def record_failure(self, connector_name: str, reason: str) -> None:
        state = dict(self._states.get(connector_name, {}))
        state["failures"] = state.get("failures", 0) + 1
        state["last_error"] = reason
        self._states[connector_name] = state

    def record_execution(self, connector_name: str, *, rows: int, elapsed_ms: float) -> None:
        state = dict(self._states.get(connector_name, {}))
        state["rows"] = rows
        state["elapsed_ms"] = elapsed_ms
        self._states[connector_name] = state

    def snapshot(self, connector_name: str) -> dict[str, Any]:
        return dict(self._states.get(connector_name, {}))
