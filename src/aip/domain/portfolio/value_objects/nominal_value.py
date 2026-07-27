"""NominalValue value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class NominalValue:
    """Represents a non-negative nominal amount in a currency."""

    money: Money

    def __post_init__(self) -> None:
        if self.money.amount < Decimal("0"):
            raise InvalidPositionError("Nominal value cannot be negative.")

    @property
    def amount(self) -> Decimal:
        """Return nominal amount."""
        return self.money.amount

    @property
    def currency(self) -> Currency:
        """Return nominal currency."""
        return self.money.currency

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: Currency) -> "NominalValue":
        """Build nominal value from amount and currency."""
        return cls(Money(amount, currency))
