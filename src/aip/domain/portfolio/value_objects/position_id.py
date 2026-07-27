"""PositionId value object."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class PositionId:
    """Typed identifier for position entities."""

    value: UUID

    @classmethod
    def new(cls) -> "PositionId":
        """Create a new position identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> "PositionId":
        """Build identifier from UUID string."""
        return cls(UUID(raw))

    def __str__(self) -> str:
        """Return UUID string representation."""
        return str(self.value)
