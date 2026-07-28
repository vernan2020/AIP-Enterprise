from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Immutable context passed to policies during evaluation."""

    context_id: str
    timestamp: datetime | None = None
    metadata: dict[str, object] | None = None
