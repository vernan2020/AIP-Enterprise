"""Money value objects for AIP Enterprise.

This module provides immutable money value objects with support for
multiple currencies, exchange rates, and arithmetic operations.

Classes:
    Currency: Currency enumeration.
    Money: Immutable money value object.
    ExchangeRate: Currency exchange rate.
    MoneyArithmetic: Arithmetic operations on money.
"""

import sys
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Self

from aip.shared.validation import Guard, Validators

sys.modules.setdefault("src.aip.shared.money", sys.modules[__name__])


class Currency(Enum):
    """Currency enumeration with ISO 4217 codes.

    References:
    - ISO 4217 Currency Codes
    """

    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro
    GBP = "GBP"  # British Pound
    JPY = "JPY"  # Japanese Yen
    CHF = "CHF"  # Swiss Franc
    CAD = "CAD"  # Canadian Dollar
    AUD = "AUD"  # Australian Dollar
    NZD = "NZD"  # New Zealand Dollar
    CNY = "CNY"  # Chinese Yuan
    CRC = "CRC"  # Costa Rican Colón

    def __str__(self) -> str:
        """String representation."""
        return self.value

    @staticmethod
    def from_code(code: str) -> Self:
        """Get currency from ISO code.

        Args:
            code: The ISO 4217 currency code.

        Returns:
            The Currency enum value.

        Raises:
            ValueError: If code is not valid.
        """
        Guard.required(code, "code")
        Guard.matches(
            code, "code", Validators.is_valid_iso_currency_code, "ISO 4217 code (e.g., 'USD')"
        )

        try:
            return Currency[code.upper()]
        except KeyError:
            raise ValueError(f"Unknown currency code: {code}")


@dataclass(frozen=True)
class Money:
    """Immutable money value object.

    Represents a monetary amount in a specific currency with
    support for arithmetic operations and comparisons.

    Attributes:
        amount: The monetary amount.
        currency: The currency of the amount.
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        """Validate initialization."""
        Guard.required(self.amount, "amount")
        Guard.required(self.currency, "currency")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.currency} {self.amount}"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"Money({self.amount}, {self.currency})"

    def __lt__(self, other: Self) -> bool:
        """Less than comparison."""
        self._validate_currency_match(other)
        return self.amount < other.amount

    def __le__(self, other: Self) -> bool:
        """Less than or equal comparison."""
        self._validate_currency_match(other)
        return self.amount <= other.amount

    def __gt__(self, other: Self) -> bool:
        """Greater than comparison."""
        self._validate_currency_match(other)
        return self.amount > other.amount

    def __ge__(self, other: Self) -> bool:
        """Greater than or equal comparison."""
        self._validate_currency_match(other)
        return self.amount >= other.amount

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash((self.amount, self.currency))

    def __add__(self, other: Self) -> Self:
        """Add money amounts.

        Args:
            other: Money to add.

        Returns:
            New Money with sum.

        Raises:
            ValueError: If currencies don't match.
        """
        self._validate_currency_match(other)
        result_amount = (self.amount + other.amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return Money(result_amount, self.currency)

    def __sub__(self, other: Self) -> Self:
        """Subtract money amounts.

        Args:
            other: Money to subtract.

        Returns:
            New Money with difference.

        Raises:
            ValueError: If currencies don't match.
        """
        self._validate_currency_match(other)
        result_amount = (self.amount - other.amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return Money(result_amount, self.currency)

    def __mul__(self, factor: Decimal | int | float) -> Self:
        """Multiply money by factor.

        Args:
            factor: The multiplication factor.

        Returns:
            New Money with multiplied amount.
        """
        if isinstance(factor, (int, float)):
            factor = Decimal(str(factor))

        result_amount = (self.amount * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Money(result_amount, self.currency)

    def __rmul__(self, factor: Decimal | int | float) -> Self:
        """Multiply money by factor (reverse).

        Args:
            factor: The multiplication factor.

        Returns:
            New Money with multiplied amount.
        """
        return self.__mul__(factor)

    def __truediv__(self, divisor: Decimal | int | float) -> Self:
        """Divide money by divisor.

        Args:
            divisor: The divisor.

        Returns:
            New Money with divided amount.

        Raises:
            ValueError: If divisor is zero.
        """
        if divisor == 0:
            raise ValueError("Cannot divide by zero")

        if isinstance(divisor, (int, float)):
            divisor = Decimal(str(divisor))

        result_amount = (self.amount / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Money(result_amount, self.currency)

    def __neg__(self) -> Self:
        """Negate money amount.

        Returns:
            New Money with negated amount.
        """
        return Money(-self.amount, self.currency)

    def abs(self) -> Self:
        """Get absolute value.

        Returns:
            New Money with absolute amount.
        """
        return Money(abs(self.amount), self.currency)

    def is_positive(self) -> bool:
        """Check if amount is positive.

        Returns:
            True if amount > 0.
        """
        return self.amount > 0

    def is_negative(self) -> bool:
        """Check if amount is negative.

        Returns:
            True if amount < 0.
        """
        return self.amount < 0

    def is_zero(self) -> bool:
        """Check if amount is zero.

        Returns:
            True if amount == 0.
        """
        return self.amount == 0

    def _validate_currency_match(self, other: Self) -> None:
        """Validate that currencies match.

        Args:
            other: Another Money object.

        Raises:
            ValueError: If currencies don't match.
        """
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot operate on different currencies: {self.currency} and {other.currency}"
            )


@dataclass(frozen=True)
class ExchangeRate:
    """Currency exchange rate value object.

    Represents an exchange rate between two currencies.

    Attributes:
        from_currency: Currency being converted from.
        to_currency: Currency being converted to.
        rate: The exchange rate.
        effective_date: Date the rate is effective.
    """

    from_currency: Currency
    to_currency: Currency
    rate: Decimal
    effective_date: date

    def __post_init__(self) -> None:
        """Validate initialization."""
        Guard.required(self.from_currency, "from_currency")
        Guard.required(self.to_currency, "to_currency")
        Guard.required(self.rate, "rate")
        Guard.required(self.effective_date, "effective_date")
        Guard.positive(self.rate, "rate")

        if self.from_currency == self.to_currency:
            raise ValueError("Cannot exchange same currency")

    def __str__(self) -> str:
        """String representation."""
        return f"1 {self.from_currency} = {self.rate} {self.to_currency}"

    def convert(self, money: Money) -> Money:
        """Convert money using exchange rate.

        Args:
            money: Money to convert.

        Returns:
            New Money in target currency.

        Raises:
            ValueError: If source currency doesn't match.
        """
        if money.currency != self.from_currency:
            raise ValueError(f"Cannot convert {money.currency} with rate for {self.from_currency}")

        converted_amount = (money.amount * self.rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return Money(converted_amount, self.to_currency)

    def inverse(self) -> Self:
        """Get inverse exchange rate.

        Returns:
            New ExchangeRate with inverse direction and rate.
        """
        if self.rate == 0:
            raise ValueError("Cannot invert zero rate")

        inverse_rate = (Decimal(1) / self.rate).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        return ExchangeRate(self.to_currency, self.from_currency, inverse_rate, self.effective_date)


class MoneyArithmetic:
    """Arithmetic operations on money amounts.

    Provides utility methods for common money calculations.
    """

    @staticmethod
    def sum_money(amounts: list[Money]) -> Money:
        """Sum a list of money amounts.

        Args:
            amounts: List of Money objects in same currency.

        Returns:
            Total of all amounts.

        Raises:
            ValueError: If list is empty or currencies don't match.
        """
        Guard.not_empty(amounts, "amounts")

        total = amounts[0]
        for amount in amounts[1:]:
            total = total + amount

        return total

    @staticmethod
    def average_money(amounts: list[Money]) -> Money:
        """Calculate average of money amounts.

        Args:
            amounts: List of Money objects in same currency.

        Returns:
            Average of amounts.

        Raises:
            ValueError: If list is empty or currencies don't match.
        """
        Guard.not_empty(amounts, "amounts")

        total = MoneyArithmetic.sum_money(amounts)
        count = Decimal(len(amounts))

        return total / count

    @staticmethod
    def multiply_money(money: Money, factor: Decimal | int | float) -> Money:
        """Multiply money by factor.

        Args:
            money: Money to multiply.
            factor: Multiplication factor.

        Returns:
            Money with multiplied amount.
        """
        return money * factor
