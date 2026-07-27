"""TransactionId value object."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class TransactionId:
    """Typed identifier for transaction entities."""

    value: UUID

    @classmethod
    def new(cls) -> "TransactionId":
        """Create a new transaction identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> "TransactionId":
        """Build identifier from UUID string."""
        return cls(UUID(raw))

    def __str__(self) -> str:
        """Return UUID string representation."""
        return str(self.value)
