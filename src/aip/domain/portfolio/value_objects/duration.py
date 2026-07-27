"""Duration value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError


@dataclass(frozen=True, slots=True)
class Duration:
    """Represents Macaulay/modified duration in years."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value < Decimal("0"):
            raise InvalidPositionError("Duration cannot be negative.")
        if self.value > Decimal("100"):
            raise InvalidPositionError("Duration is out of acceptable range.")
