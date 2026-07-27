"""PortfolioId value object."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class PortfolioId:
    """Typed identifier for portfolio aggregates."""

    value: UUID

    @classmethod
    def new(cls) -> "PortfolioId":
        """Create a new portfolio identifier."""
        return cls(uuid4())

    @classmethod
    def from_string(cls, raw: str) -> "PortfolioId":
        """Build identifier from UUID string."""
        return cls(UUID(raw))

    def __str__(self) -> str:
        """Return UUID string representation."""
        return str(self.value)
