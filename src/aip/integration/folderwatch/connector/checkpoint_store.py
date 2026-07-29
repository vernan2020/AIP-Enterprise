from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InMemoryCheckpointStore:
    """Simple in-memory checkpoint store for folder processing state."""

    checkpoints: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def save(self, job_id: str, filename: str, state: dict[str, Any]) -> None:
        self.checkpoints.setdefault(job_id, {})[filename] = state

    def get(self, job_id: str, filename: str) -> dict[str, Any] | None:
        return self.checkpoints.get(job_id, {}).get(filename)

    def list(self, job_id: str) -> list[str]:
        return list(self.checkpoints.get(job_id, {}).keys())
