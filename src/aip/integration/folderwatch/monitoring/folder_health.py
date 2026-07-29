from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FolderHealthMonitor:
    """Tracks folder watch health counters and state."""

    files_detected: dict[str, int] = field(default_factory=dict)
    files_processed: dict[str, int] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    latencies: dict[str, float] = field(default_factory=dict)
    states: dict[str, str] = field(default_factory=dict)

    def record_detection(self, connector_name: str, count: int) -> None:
        self.files_detected[connector_name] = self.files_detected.get(connector_name, 0) + count

    def record_processed(self, connector_name: str, count: int) -> None:
        self.files_processed[connector_name] = self.files_processed.get(connector_name, 0) + count

    def record_failure(self, connector_name: str) -> None:
        self.failures[connector_name] = self.failures.get(connector_name, 0) + 1

    def record_retry(self, connector_name: str) -> None:
        self.retries[connector_name] = self.retries.get(connector_name, 0) + 1

    def record_latency(self, connector_name: str, elapsed_ms: float) -> None:
        self.latencies[connector_name] = elapsed_ms

    def record_state(self, connector_name: str, state: str) -> None:
        self.states[connector_name] = state

    def snapshot(self, connector_name: str) -> dict[str, object]:
        return {
            "files_detected": self.files_detected.get(connector_name, 0),
            "files_processed": self.files_processed.get(connector_name, 0),
            "failures": self.failures.get(connector_name, 0),
            "retries": self.retries.get(connector_name, 0),
            "latency_ms": self.latencies.get(connector_name, 0.0),
            "state": self.states.get(connector_name, "stopped"),
        }
