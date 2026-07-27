"""Base immutable domain event object."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable domain event contract for portfolio bounded context."""

    event_id: str
    occurred_at: datetime
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> "DomainEvent":
        """Create a domain event with generated id and UTC timestamp."""
        return cls(
            event_id=str(uuid4()),
            occurred_at=datetime.now(timezone.utc),
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
