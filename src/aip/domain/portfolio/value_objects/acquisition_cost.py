"""AcquisitionCost value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class AcquisitionCost:
    """Represents a non-negative acquisition cost in a currency."""

    money: Money

    def __post_init__(self) -> None:
        if self.money.amount < Decimal("0"):
            raise InvalidPositionError("Acquisition cost cannot be negative.")

    @property
    def amount(self) -> Decimal:
        """Return acquisition cost amount."""
        return self.money.amount

    @property
    def currency(self) -> Currency:
        """Return acquisition cost currency."""
        return self.money.currency

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: Currency) -> "AcquisitionCost":
        """Build acquisition cost from amount and currency."""
        return cls(Money(amount, currency))
