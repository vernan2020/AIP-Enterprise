"""Convexity value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError


@dataclass(frozen=True, slots=True)
class Convexity:
    """Represents validated convexity for fixed-income analytics."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value < Decimal("0"):
            raise InvalidPositionError("Convexity cannot be negative.")
        if self.value > Decimal("1000"):
            raise InvalidPositionError("Convexity is out of acceptable range.")
