"""InstrumentName value object."""

from dataclasses import dataclass

from src.aip.domain.portfolio.exceptions import InvalidPositionError


@dataclass(frozen=True, slots=True)
class InstrumentName:
    """Represents a normalized instrument display name."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        object.__setattr__(self, "value", normalized)

        if not normalized:
            raise InvalidPositionError("Instrument name cannot be empty.")
        if len(normalized) > 200:
            raise InvalidPositionError("Instrument name cannot exceed 200 characters.")

    def __str__(self) -> str:
        """Return instrument name string."""
        return self.value
