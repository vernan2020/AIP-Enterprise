"""Position added domain event."""

from dataclasses import dataclass

from src.aip.domain.portfolio.events.domain_event import DomainEvent


@dataclass(frozen=True, slots=True)
class PositionAdded(DomainEvent):
    """Event emitted when a position is added to a portfolio."""

    @classmethod
    def from_payload(cls, aggregate_id: str, payload: dict[str, object]) -> "PositionAdded":
        """Create position-added event from payload."""
        base = DomainEvent.create(
            aggregate_id=aggregate_id,
            event_type="portfolio.position_added",
            payload=payload,
        )
        return cls(
            event_id=base.event_id,
            occurred_at=base.occurred_at,
            aggregate_id=base.aggregate_id,
            event_type=base.event_type,
            payload=base.payload,
        )
