"""YieldRate value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.shared.math import Percentage


@dataclass(frozen=True, slots=True)
class YieldRate:
    """Represents a validated yield percentage."""

    value: Percentage

    def __post_init__(self) -> None:
        if self.value.value < Decimal("-100"):
            raise InvalidPositionError("Yield rate cannot be lower than -100%.")
        if self.value.value > Decimal("1000"):
            raise InvalidPositionError("Yield rate cannot exceed 1000%.")

    @property
    def decimal(self) -> Decimal:
        """Return yield in decimal form."""
        return self.value.as_decimal()

    @classmethod
    def from_decimal_percentage(cls, value: Decimal) -> "YieldRate":
        """Build yield rate from percentage number."""
        return cls(Percentage(value))
