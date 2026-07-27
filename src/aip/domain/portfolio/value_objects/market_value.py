"""MarketValue value object."""

from dataclasses import dataclass
from decimal import Decimal

from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class MarketValue:
    """Represents a non-negative market value in a currency."""

    money: Money

    def __post_init__(self) -> None:
        if self.money.amount < Decimal("0"):
            raise InvalidPositionError("Market value cannot be negative.")

    @property
    def amount(self) -> Decimal:
        """Return market value amount."""
        return self.money.amount

    @property
    def currency(self) -> Currency:
        """Return market value currency."""
        return self.money.currency

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: Currency) -> "MarketValue":
        """Build market value from amount and currency."""
        return cls(Money(amount, currency))
