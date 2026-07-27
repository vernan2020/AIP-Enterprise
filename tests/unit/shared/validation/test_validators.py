"""Tests for validation module.

Comprehensive tests for Guard clauses and Validators utility.
"""

import pytest
from decimal import Decimal

from src.aip.shared.validation import (
    Guard,
    Validators,
    ValidationException,
    RequiredValueError,
    PositiveValueError,
    NotEmptyError,
    RangeError,
    InvalidFormatError,
)


class TestGuardRequired:
    """Tests for Guard.required() method."""
    
    def test_required_with_value_returns_value(self) -> None:
        """Test that required() returns value when not None."""
        result = Guard.required("test", "field")
        assert result == "test"
    
    def test_required_with_none_raises_error(self) -> None:
        """Test that required() raises RequiredValueError when None."""
        with pytest.raises(RequiredValueError) as exc_info:
            Guard.required(None, "field")
        assert exc_info.value.field_name == "field"
    
    def test_required_with_zero_returns_zero(self) -> None:
        """Test that required() returns 0 (falsy but valid value)."""
        result = Guard.required(0, "field")
        assert result == 0
    
    def test_required_with_empty_string_returns_empty_string(self) -> None:
        """Test that required() returns empty string (falsy but valid)."""
        result = Guard.required("", "field")
        assert result == ""


class TestGuardNotEmpty:
    """Tests for Guard.not_empty() method."""
    
    def test_not_empty_with_non_empty_string(self) -> None:
        """Test that not_empty() returns string when not empty."""
        result = Guard.not_empty("test", "field")
        assert result == "test"
    
    def test_not_empty_with_empty_string_raises_error(self) -> None:
        """Test that not_empty() raises NotEmptyError for empty string."""
        with pytest.raises(NotEmptyError):
            Guard.not_empty("", "field")
    
    def test_not_empty_with_non_empty_list(self) -> None:
        """Test that not_empty() returns list when not empty."""
        test_list = [1, 2, 3]
        result = Guard.not_empty(test_list, "field")
        assert result == test_list
    
    def test_not_empty_with_empty_list_raises_error(self) -> None:
        """Test that not_empty() raises NotEmptyError for empty list."""
        with pytest.raises(NotEmptyError):
            Guard.not_empty([], "field")


class TestGuardPositive:
    """Tests for Guard.positive() method."""
    
    def test_positive_with_positive_int(self) -> None:
        """Test that positive() returns positive integer."""
        result = Guard.positive(5, "field")
        assert result == 5
    
    def test_positive_with_positive_decimal(self) -> None:
        """Test that positive() returns positive Decimal."""
        value = Decimal("5.5")
        result = Guard.positive(value, "field")
        assert result == value
    
    def test_positive_with_zero_raises_error(self) -> None:
        """Test that positive() raises PositiveValueError for zero."""
        with pytest.raises(PositiveValueError):
            Guard.positive(0, "field")
    
    def test_positive_with_negative_raises_error(self) -> None:
        """Test that positive() raises PositiveValueError for negative."""
        with pytest.raises(PositiveValueError):
            Guard.positive(-5, "field")


class TestGuardNonNegative:
    """Tests for Guard.non_negative() method."""
    
    def test_non_negative_with_positive_value(self) -> None:
        """Test that non_negative() returns positive value."""
        result = Guard.non_negative(5, "field")
        assert result == 5
    
    def test_non_negative_with_zero(self) -> None:
        """Test that non_negative() returns zero."""
        result = Guard.non_negative(0, "field")
        assert result == 0
    
    def test_non_negative_with_negative_raises_error(self) -> None:
        """Test that non_negative() raises PositiveValueError for negative."""
        with pytest.raises(PositiveValueError):
            Guard.non_negative(-5, "field")


class TestGuardInRange:
    """Tests for Guard.in_range() method."""
    
    def test_in_range_with_value_in_range(self) -> None:
        """Test that in_range() returns value when in range."""
        result = Guard.in_range(5, "field", Decimal("0"), Decimal("10"))
        assert result == 5
    
    def test_in_range_with_value_below_min_raises_error(self) -> None:
        """Test that in_range() raises RangeError when below min."""
        with pytest.raises(RangeError):
            Guard.in_range(5, "field", Decimal("10"), Decimal("20"))
    
    def test_in_range_with_value_above_max_raises_error(self) -> None:
        """Test that in_range() raises RangeError when above max."""
        with pytest.raises(RangeError):
            Guard.in_range(25, "field", Decimal("10"), Decimal("20"))
    
    def test_in_range_with_only_min(self) -> None:
        """Test in_range with only minimum value."""
        result = Guard.in_range(15, "field", Decimal("10"))
        assert result == 15
    
    def test_in_range_with_only_max(self) -> None:
        """Test in_range with only maximum value."""
        result = Guard.in_range(5, "field", max_value=Decimal("10"))
        assert result == 5


class TestGuardMatches:
    """Tests for Guard.matches() method."""
    
    def test_matches_with_valid_pattern(self) -> None:
        """Test that matches() returns value when pattern matches."""
        result = Guard.matches("AAPL", "ticker", lambda x: len(x) <= 5, "max 5 chars")
        assert result == "AAPL"
    
    def test_matches_with_invalid_pattern_raises_error(self) -> None:
        """Test that matches() raises InvalidFormatError when pattern fails."""
        with pytest.raises(InvalidFormatError):
            Guard.matches("TOOLONG", "ticker", lambda x: len(x) <= 5, "max 5 chars")


class TestValidators:
    """Tests for Validators utility class."""
    
    def test_is_positive_with_positive_value(self) -> None:
        """Test is_positive returns True for positive value."""
        assert Validators.is_positive(5) is True
    
    def test_is_positive_with_zero(self) -> None:
        """Test is_positive returns False for zero."""
        assert Validators.is_positive(0) is False
    
    def test_is_positive_with_negative_value(self) -> None:
        """Test is_positive returns False for negative."""
        assert Validators.is_positive(-5) is False
    
    def test_is_non_negative_with_positive_value(self) -> None:
        """Test is_non_negative returns True for positive."""
        assert Validators.is_non_negative(5) is True
    
    def test_is_non_negative_with_zero(self) -> None:
        """Test is_non_negative returns True for zero."""
        assert Validators.is_non_negative(0) is True
    
    def test_is_non_negative_with_negative_value(self) -> None:
        """Test is_non_negative returns False for negative."""
        assert Validators.is_non_negative(-5) is False
    
    def test_is_in_range_with_value_in_range(self) -> None:
        """Test is_in_range returns True when in range."""
        assert Validators.is_in_range(5, Decimal("0"), Decimal("10")) is True
    
    def test_is_in_range_with_value_out_of_range(self) -> None:
        """Test is_in_range returns False when out of range."""
        assert Validators.is_in_range(15, Decimal("0"), Decimal("10")) is False
    
    def test_is_not_empty_with_non_empty_string(self) -> None:
        """Test is_not_empty returns True for non-empty string."""
        assert Validators.is_not_empty("test") is True
    
    def test_is_not_empty_with_empty_string(self) -> None:
        """Test is_not_empty returns False for empty string."""
        assert Validators.is_not_empty("") is False
    
    def test_is_valid_iso_currency_code_valid(self) -> None:
        """Test is_valid_iso_currency_code returns True for valid code."""
        assert Validators.is_valid_iso_currency_code("USD") is True
        assert Validators.is_valid_iso_currency_code("EUR") is True
    
    def test_is_valid_iso_currency_code_invalid(self) -> None:
        """Test is_valid_iso_currency_code returns False for invalid codes."""
        assert Validators.is_valid_iso_currency_code("US") is False  # Too short
        assert Validators.is_valid_iso_currency_code("USDA") is False  # Too long
        assert Validators.is_valid_iso_currency_code("usd") is False  # Lowercase
    
    def test_is_valid_ticker_valid(self) -> None:
        """Test is_valid_ticker returns True for valid tickers."""
        assert Validators.is_valid_ticker("AAPL") is True
        assert Validators.is_valid_ticker("MSFT") is True
        assert Validators.is_valid_ticker("A") is True
    
    def test_is_valid_ticker_invalid(self) -> None:
        """Test is_valid_ticker returns False for invalid tickers."""
        assert Validators.is_valid_ticker("") is False  # Empty
        assert Validators.is_valid_ticker("TOOLONG") is False  # Too long
        assert Validators.is_valid_ticker("aapl") is False  # Lowercase
        assert Validators.is_valid_ticker("A1") is False  # Contains number


class TestValidationExceptions:
    """Tests for validation exception types."""
    
    def test_required_value_error_properties(self) -> None:
        """Test RequiredValueError has correct properties."""
        error = RequiredValueError("field")
        assert error.field_name == "field"
        assert "field" in error.message
    
    def test_positive_value_error_properties(self) -> None:
        """Test PositiveValueError has correct properties."""
        error = PositiveValueError("amount", -5)
        assert error.field_name == "amount"
        assert "-5" in error.message
    
    def test_range_error_properties(self) -> None:
        """Test RangeError has correct properties."""
        error = RangeError("rate", 15, 0, 10)
        assert error.field_name == "rate"
        assert "15" in error.message

    def test_range_error_with_max_only(self) -> None:
        """Test RangeError message when only max_value is provided."""
        error = RangeError("score", 101, max_value=100)
        assert error.field_name == "score"
        assert "must be <= 100" in str(error)
