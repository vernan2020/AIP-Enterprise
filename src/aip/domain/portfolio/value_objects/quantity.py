"""Quantity value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError


@dataclass(frozen=True, slots=True)
class Quantity:
    """Represents a strictly positive instrument quantity."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value <= Decimal("0"):
            raise InvalidPositionError("Quantity must be positive.")

    def __str__(self) -> str:
        """Return quantity as string."""
        return str(self.value)
