"""Validators and Guard clauses for input validation.

This module provides assertion-style guards and reusable validators
for enforcing business rules and data integrity.

Classes:
    Guard: Assertion methods for validation.
    Validators: Collection of reusable validation functions.
"""

from decimal import Decimal
from typing import Any, Callable, Sequence, TypeVar

from aip.shared.validation.exceptions import (
    InvalidFormatError,
    NotEmptyError,
    PositiveValueError,
    RangeError,
    RequiredValueError,
)

T = TypeVar("T")


class Guard:
    """Guard clauses for validation using assertion-style methods."""

    @staticmethod
    def required(value: T, field_name: str) -> T:
        """Assert that value is not None.

        Args:
            value: The value to check.
            field_name: The name of the field for error messages.

        Returns:
            The value if valid.

        Raises:
            RequiredValueError: If value is None.

        Example:
            >>> name = Guard.required(user.name, "name")
        """
        if value is None:
            raise RequiredValueError(field_name)
        return value

    @staticmethod
    def not_empty(
        value: str | Sequence[Any],
        field_name: str,
    ) -> str | Sequence[Any]:
        """Assert that string or sequence is not empty.

        Args:
            value: The string or sequence to check.
            field_name: The name of the field for error messages.

        Returns:
            The value if valid.

        Raises:
            NotEmptyError: If value is empty.

        Example:
            >>> name = Guard.not_empty(user.name, "name")
        """
        if not value:
            raise NotEmptyError(field_name)
        return value

    @staticmethod
    def positive(
        value: int | float | Decimal,
        field_name: str,
    ) -> int | float | Decimal:
        """Assert that value is positive (> 0).

        Args:
            value: The numeric value to check.
            field_name: The name of the field for error messages.

        Returns:
            The value if valid.

        Raises:
            PositiveValueError: If value is not positive.

        Example:
            >>> quantity = Guard.positive(order.quantity, "quantity")
        """
        if value <= 0:
            raise PositiveValueError(field_name, value)
        return value

    @staticmethod
    def non_negative(
        value: int | float | Decimal,
        field_name: str,
    ) -> int | float | Decimal:
        """Assert that value is non-negative (>= 0).

        Args:
            value: The numeric value to check.
            field_name: The name of the field for error messages.

        Returns:
            The value if valid.

        Raises:
            PositiveValueError: If value is negative.

        Example:
            >>> balance = Guard.non_negative(account.balance, "balance")
        """
        if value < 0:
            raise PositiveValueError(field_name, value)
        return value

    @staticmethod
    def in_range(
        value: int | float | Decimal,
        field_name: str,
        min_value: int | float | Decimal | None = None,
        max_value: int | float | Decimal | None = None,
    ) -> int | float | Decimal:
        """Assert that value is within specified range.

        Args:
            value: The value to check.
            field_name: The name of the field for error messages.
            min_value: Minimum acceptable value (inclusive).
            max_value: Maximum acceptable value (inclusive).

        Returns:
            The value if valid.

        Raises:
            RangeError: If value is outside range.

        Example:
            >>> rate = Guard.in_range(coupon_rate, "rate", Decimal("0"), Decimal("100"))
        """
        if min_value is not None and value < min_value:
            raise RangeError(field_name, value, min_value, max_value)
        if max_value is not None and value > max_value:
            raise RangeError(field_name, value, min_value, max_value)
        return value

    @staticmethod
    def matches(
        value: str,
        field_name: str,
        pattern: Callable[[str], bool],
        format_description: str = "pattern",
    ) -> str:
        """Assert that string matches validation pattern.

        Args:
            value: The string to validate.
            field_name: The name of the field for error messages.
            pattern: Function that returns True if pattern matches.
            format_description: Description of expected format.

        Returns:
            The value if valid.

        Raises:
            InvalidFormatError: If pattern doesn't match.

        Example:
            >>> ticker = Guard.matches(
            ...     value,
            ...     "ticker",
            ...     lambda x: len(x) <= 5,
            ...     "max 5 characters"
            ... )
        """
        if not pattern(value):
            raise InvalidFormatError(field_name, format_description)
        return value


class Validators:
    """Collection of reusable validation functions."""

    @staticmethod
    def is_positive(value: int | float | Decimal) -> bool:
        """Check if value is positive.

        Args:
            value: The value to check.

        Returns:
            True if value > 0, False otherwise.
        """
        return value > 0

    @staticmethod
    def is_non_negative(value: int | float | Decimal) -> bool:
        """Check if value is non-negative.

        Args:
            value: The value to check.

        Returns:
            True if value >= 0, False otherwise.
        """
        return value >= 0

    @staticmethod
    def is_in_range(
        value: int | float | Decimal,
        min_value: int | float | Decimal | None = None,
        max_value: int | float | Decimal | None = None,
    ) -> bool:
        """Check if value is within range.

        Args:
            value: The value to check.
            min_value: Minimum acceptable value.
            max_value: Maximum acceptable value.

        Returns:
            True if value is in range, False otherwise.
        """
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True

    @staticmethod
    def is_not_empty(value: str | Sequence[Any]) -> bool:
        """Check if string or sequence is not empty.

        Args:
            value: The value to check.

        Returns:
            True if value is not empty, False otherwise.
        """
        return bool(value)

    @staticmethod
    def is_valid_iso_currency_code(code: str) -> bool:
        """Check if string is valid ISO 4217 currency code.

        Args:
            code: The currency code to validate.

        Returns:
            True if valid format, False otherwise.

        Example:
            >>> Validators.is_valid_iso_currency_code("USD")
            True
            >>> Validators.is_valid_iso_currency_code("invalid")
            False
        """
        return len(code) == 3 and code.isupper()

    @staticmethod
    def is_valid_ticker(ticker: str) -> bool:
        """Check if string is valid security ticker symbol.

        Args:
            ticker: The ticker to validate.

        Returns:
            True if valid format, False otherwise.

        Example:
            >>> Validators.is_valid_ticker("AAPL")
            True
            >>> Validators.is_valid_ticker("A" * 10)
            False
        """
        return 1 <= len(ticker) <= 5 and ticker.isupper() and ticker.isalpha()
