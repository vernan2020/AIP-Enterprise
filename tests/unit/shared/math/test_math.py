"""Tests for math module.

Comprehensive tests for SafeDecimal, Percentage, WeightedAverage, and Interpolation.
"""

import pytest
from decimal import Decimal, InvalidOperation

from src.aip.shared.math import (
    SafeDecimal,
    Percentage,
    WeightedAverage,
    LinearInterpolation,
)


class TestSafeDecimal:
    """Tests for SafeDecimal class."""
    
    def test_safe_decimal_creation(self) -> None:
        """Test SafeDecimal can be created."""
        sd = SafeDecimal(Decimal("123.45"))
        assert sd.value == Decimal("123.45")
        assert sd.precision == 2
    
    def test_safe_decimal_quantize(self) -> None:
        """Test quantize method."""
        sd = SafeDecimal(Decimal("123.456"))
        result = sd.quantize()
        assert result == Decimal("123.46")
    
    def test_safe_decimal_add(self) -> None:
        """Test addition."""
        sd1 = SafeDecimal(Decimal("100"))
        sd2 = SafeDecimal(Decimal("50"))
        result = sd1.add(sd2)
        assert result.value == Decimal("150")
    
    def test_safe_decimal_subtract(self) -> None:
        """Test subtraction."""
        sd1 = SafeDecimal(Decimal("100"))
        sd2 = SafeDecimal(Decimal("50"))
        result = sd1.subtract(sd2)
        assert result.value == Decimal("50")
    
    def test_safe_decimal_multiply(self) -> None:
        """Test multiplication."""
        sd = SafeDecimal(Decimal("100"))
        result = sd.multiply(Decimal("1.5"))
        assert result.value == Decimal("150")
    
    def test_safe_decimal_divide(self) -> None:
        """Test division."""
        sd = SafeDecimal(Decimal("100"))
        result = sd.divide(Decimal("2"))
        assert result.value == Decimal("50")
    
    def test_safe_decimal_divide_by_zero_raises_error(self) -> None:
        """Test division by zero raises error."""
        sd = SafeDecimal(Decimal("100"))
        with pytest.raises(InvalidOperation):
            sd.divide(Decimal("0"))
    
    def test_safe_decimal_power(self) -> None:
        """Test power operation."""
        sd = SafeDecimal(Decimal("2"))
        result = sd.power(3)
        assert result.value == Decimal("8")
    
    def test_safe_decimal_square_root(self) -> None:
        """Test square root operation."""
        sd = SafeDecimal(Decimal("4"))
        result = sd.square_root()
        assert result.value == Decimal("2")
    
    def test_safe_decimal_square_root_negative_raises_error(self) -> None:
        """Test square root of negative raises error."""
        sd = SafeDecimal(Decimal("-4"))
        with pytest.raises(InvalidOperation):
            sd.square_root()


class TestPercentage:
    """Tests for Percentage value object."""
    
    def test_percentage_creation(self) -> None:
        """Test Percentage can be created."""
        pct = Percentage(Decimal("5.5"))
        assert pct.value == Decimal("5.5")
    
    def test_percentage_string_representation(self) -> None:
        """Test string representation."""
        pct = Percentage(Decimal("5.5"))
        assert str(pct) == "5.5%"
    
    def test_percentage_comparison(self) -> None:
        """Test comparison operations."""
        pct1 = Percentage(Decimal("5"))
        pct2 = Percentage(Decimal("10"))
        assert pct1 < pct2
        assert pct1 <= pct2
        assert pct2 > pct1
        assert pct2 >= pct1
    
    def test_percentage_equality(self) -> None:
        """Test equality comparison."""
        pct1 = Percentage(Decimal("5"))
        pct2 = Percentage(Decimal("5"))
        pct3 = Percentage(Decimal("10"))
        assert pct1 == pct2
        assert pct1 != pct3
    
    def test_percentage_hash(self) -> None:
        """Test percentage can be hashed."""
        pct1 = Percentage(Decimal("5"))
        pct2 = Percentage(Decimal("5"))
        assert hash(pct1) == hash(pct2)
    
    def test_percentage_as_decimal(self) -> None:
        """Test as_decimal converts to decimal multiplier."""
        pct = Percentage(Decimal("10"))
        result = pct.as_decimal()
        assert result == Decimal("0.1")
    
    def test_percentage_apply_to_value(self) -> None:
        """Test apply_to applies percentage to value."""
        pct = Percentage(Decimal("10"))
        result = pct.apply_to(Decimal("100"))
        assert result == Decimal("110")


class TestWeightedAverage:
    """Tests for WeightedAverage calculator."""
    
    def test_weighted_average_calculation(self) -> None:
        """Test weighted average calculation."""
        calc = WeightedAverage()
        values = [Decimal("100"), Decimal("200")]
        weights = [Decimal("0.3"), Decimal("0.7")]
        result = calc.calculate(values, weights)
        assert result == Decimal("170.00")
    
    def test_weighted_average_single_value(self) -> None:
        """Test weighted average with single value."""
        calc = WeightedAverage()
        values = [Decimal("100")]
        weights = [Decimal("1")]
        result = calc.calculate(values, weights)
        assert result == Decimal("100.00")
    
    def test_weighted_average_mismatched_lengths_raises_error(self) -> None:
        """Test mismatched lengths raises error."""
        calc = WeightedAverage()
        values = [Decimal("100"), Decimal("200")]
        weights = [Decimal("0.5")]
        with pytest.raises(ValueError):
            calc.calculate(values, weights)
    
    def test_weighted_average_invalid_weights_raises_error(self) -> None:
        """Test weights not summing to 1 raises error."""
        calc = WeightedAverage()
        values = [Decimal("100"), Decimal("200")]
        weights = [Decimal("0.3"), Decimal("0.3")]  # Sum is 0.6, not 1
        with pytest.raises(ValueError):
            calc.calculate(values, weights)
    
    def test_weighted_average_empty_list_raises_error(self) -> None:
        """Test empty list raises error."""
        calc = WeightedAverage()
        with pytest.raises(Exception):  # NotEmptyError from Guard
            calc.calculate([], [])


class TestLinearInterpolation:
    """Tests for LinearInterpolation utility."""
    
    def test_interpolate_at_first_point(self) -> None:
        """Test interpolation at first point."""
        result = LinearInterpolation.interpolate(
            Decimal("2"),
            Decimal("2"),
            Decimal("100"),
            Decimal("3"),
            Decimal("110")
        )
        assert result == Decimal("100.00")
    
    def test_interpolate_at_second_point(self) -> None:
        """Test interpolation at second point."""
        result = LinearInterpolation.interpolate(
            Decimal("3"),
            Decimal("2"),
            Decimal("100"),
            Decimal("3"),
            Decimal("110")
        )
        assert result == Decimal("110.00")
    
    def test_interpolate_midpoint(self) -> None:
        """Test interpolation at midpoint."""
        result = LinearInterpolation.interpolate(
            Decimal("2.5"),
            Decimal("2"),
            Decimal("100"),
            Decimal("3"),
            Decimal("110")
        )
        assert result == Decimal("105.00")
    
    def test_interpolate_outside_range(self) -> None:
        """Test interpolation outside range."""
        result = LinearInterpolation.interpolate(
            Decimal("4"),
            Decimal("2"),
            Decimal("100"),
            Decimal("3"),
            Decimal("110")
        )
        assert result == Decimal("120.00")
    
    def test_interpolate_equal_x_values_raises_error(self) -> None:
        """Test equal x values raises error."""
        with pytest.raises(ValueError):
            LinearInterpolation.interpolate(
                Decimal("2.5"),
                Decimal("2"),
                Decimal("100"),
                Decimal("2"),
                Decimal("110")
            )
    
    def test_interpolate_curve_simple(self) -> None:
        """Test curve interpolation."""
        points = [
            (Decimal("1"), Decimal("10")),
            (Decimal("2"), Decimal("20")),
            (Decimal("3"), Decimal("30")),
        ]
        result = LinearInterpolation.interpolate_curve(Decimal("1.5"), points)
        assert result == Decimal("15.00")
    
    def test_interpolate_curve_before_first_point(self) -> None:
        """Test interpolation before first point returns first value."""
        points = [
            (Decimal("1"), Decimal("10")),
            (Decimal("2"), Decimal("20")),
        ]
        result = LinearInterpolation.interpolate_curve(Decimal("0"), points)
        assert result == Decimal("10")
    
    def test_interpolate_curve_after_last_point(self) -> None:
        """Test interpolation after last point returns last value."""
        points = [
            (Decimal("1"), Decimal("10")),
            (Decimal("2"), Decimal("20")),
        ]
        result = LinearInterpolation.interpolate_curve(Decimal("3"), points)
        assert result == Decimal("20")
    
    def test_interpolate_curve_insufficient_points_raises_error(self) -> None:
        """Test insufficient points raises error."""
        points = [(Decimal("1"), Decimal("10"))]
        with pytest.raises(ValueError):
            LinearInterpolation.interpolate_curve(Decimal("1.5"), points)
