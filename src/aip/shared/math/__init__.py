"""Math utilities for AIP Enterprise.

This module provides safe mathematical operations, percentage calculations,
weighted averages, and interpolation methods suitable for financial calculations.

Classes:
    SafeDecimal: Decimal wrapper with safe operations.
    Percentage: Immutable percentage value object.
    WeightedAverage: Calculator for weighted averages.
    LinearInterpolation: Linear interpolation between points.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Self, Sequence

from aip.shared.validation import Guard
from aip.shared.validation import Validators as Validators


@dataclass(frozen=True)
class SafeDecimal:
    """Safe Decimal wrapper for financial calculations.

    Provides methods for common operations with proper error handling
    and precision control suitable for financial applications.

    Attributes:
        value: The underlying Decimal value.
        precision: Number of decimal places for rounding.
    """

    value: Decimal
    precision: int = 2

    def __post_init__(self) -> None:
        """Validate initialization parameters."""
        Guard.required(self.value, "value")
        Guard.in_range(self.precision, "precision", 0, 10)

    def __str__(self) -> str:
        """String representation."""
        return str(self.quantize())

    def quantize(self) -> Decimal:
        """Quantize value to configured precision.

        Returns:
            Quantized Decimal value.
        """
        if self.precision == 0:
            quantizer = Decimal("1")
        else:
            quantizer = Decimal(10) ** -self.precision

        return self.value.quantize(quantizer, rounding=ROUND_HALF_UP)

    def add(self, other: Decimal | Self) -> Self:
        """Add safely.

        Args:
            other: Value to add.

        Returns:
            New SafeDecimal with result.
        """
        other_val = other.value if isinstance(other, SafeDecimal) else other
        result = self.value + other_val
        return SafeDecimal(result, self.precision)

    def subtract(self, other: Decimal | Self) -> Self:
        """Subtract safely.

        Args:
            other: Value to subtract.

        Returns:
            New SafeDecimal with result.
        """
        other_val = other.value if isinstance(other, SafeDecimal) else other
        result = self.value - other_val
        return SafeDecimal(result, self.precision)

    def multiply(self, other: Decimal | Self | int | float) -> Self:
        """Multiply safely.

        Args:
            other: Value to multiply by.

        Returns:
            New SafeDecimal with result.
        """
        if isinstance(other, SafeDecimal):
            other_val = other.value
        elif isinstance(other, (int, float)):
            other_val = Decimal(str(other))
        else:
            other_val = other

        result = self.value * other_val
        return SafeDecimal(result, self.precision)

    def divide(self, other: Decimal | Self) -> Self:
        """Divide safely.

        Args:
            other: Value to divide by.

        Returns:
            New SafeDecimal with result.

        Raises:
            InvalidOperation: If dividing by zero.
        """
        other_val = other.value if isinstance(other, SafeDecimal) else other

        if other_val == 0:
            raise InvalidOperation("Cannot divide by zero")

        result = self.value / other_val
        return SafeDecimal(result, self.precision)

    def power(self, exponent: int | float | Decimal) -> Self:
        """Raise to power safely.

        Args:
            exponent: The exponent.

        Returns:
            New SafeDecimal with result.
        """
        exp_val = Decimal(str(exponent)) if not isinstance(exponent, Decimal) else exponent
        result = self.value**exp_val
        return SafeDecimal(result, self.precision)

    def square_root(self) -> Self:
        """Calculate square root safely.

        Returns:
            New SafeDecimal with result.

        Raises:
            InvalidOperation: If value is negative.
        """
        if self.value < 0:
            raise InvalidOperation("Cannot take square root of negative value")

        result = self.value.sqrt()
        return SafeDecimal(result, self.precision)


@dataclass(frozen=True)
class Percentage:
    """Immutable percentage value object.

    Represents a percentage as a Decimal value with methods for
    arithmetic and comparison operations.

    Attributes:
        value: The percentage value (e.g., 5.5 for 5.5%).
    """

    value: Decimal

    def __post_init__(self) -> None:
        """Validate percentage value."""
        Guard.required(self.value, "value")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.value}%"

    def __lt__(self, other: Self) -> bool:
        """Less than comparison."""
        return self.value < other.value

    def __le__(self, other: Self) -> bool:
        """Less than or equal comparison."""
        return self.value <= other.value

    def __gt__(self, other: Self) -> bool:
        """Greater than comparison."""
        return self.value > other.value

    def __ge__(self, other: Self) -> bool:
        """Greater than or equal comparison."""
        return self.value >= other.value

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, Percentage):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash(self.value)

    def as_decimal(self) -> Decimal:
        """Get percentage as decimal multiplier.

        Returns:
            Percentage as decimal (e.g., 5.5% -> 0.055).
        """
        return self.value / 100

    def apply_to(self, value: Decimal) -> Decimal:
        """Apply percentage to a value.

        Args:
            value: The base value.

        Returns:
            The value increased by this percentage.

        Example:
            >>> pct = Percentage(Decimal("10"))
            >>> pct.apply_to(Decimal("100"))
            Decimal("110")
        """
        return value * (1 + self.as_decimal())


@dataclass(frozen=True)
class WeightedAverage:
    """Calculator for weighted averages.

    Computes weighted averages given values and their weights.
    """

    def __init__(self) -> None:
        """Initialize weighted average calculator."""

    def calculate(
        self,
        values: Sequence[Decimal],
        weights: Sequence[Decimal],
    ) -> Decimal:
        """Calculate weighted average.

        Args:
            values: Sequence of values.
            weights: Sequence of weights (should sum to 1).

        Returns:
            The weighted average.

        Raises:
            ValueError: If lengths don't match or weights don't sum to 1.

        Example:
            >>> calc = WeightedAverage()
            >>> values = [Decimal("100"), Decimal("200")]
            >>> weights = [Decimal("0.3"), Decimal("0.7")]
            >>> calc.calculate(values, weights)
            Decimal('170')
        """
        Guard.not_empty(values, "values")
        Guard.not_empty(weights, "weights")

        if len(values) != len(weights):
            raise ValueError("Values and weights must have same length")

        # Verify weights sum to approximately 1
        weight_sum = sum(weights)
        if not (Decimal("0.99") <= weight_sum <= Decimal("1.01")):
            raise ValueError(f"Weights must sum to 1, got {weight_sum}")

        # Calculate weighted average
        total = sum(v * w for v, w in zip(values, weights))
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LinearInterpolation:
    """Linear interpolation between points.

    Performs linear interpolation to estimate values between known points.
    """

    @staticmethod
    def interpolate(
        x: Decimal,
        x0: Decimal,
        y0: Decimal,
        x1: Decimal,
        y1: Decimal,
    ) -> Decimal:
        """Interpolate y value for given x using two known points.

        Uses linear interpolation formula: y = y0 + (x - x0) * (y1 - y0) / (x1 - x0)

        Args:
            x: The x value to interpolate.
            x0: First point x coordinate.
            y0: First point y coordinate.
            x1: Second point x coordinate.
            y1: Second point y coordinate.

        Returns:
            The interpolated y value.

        Raises:
            ValueError: If x0 == x1 (undefined slope).

        Example:
            >>> LinearInterpolation.interpolate(
            ...     Decimal("2.5"),
            ...     Decimal("2"),
            ...     Decimal("100"),
            ...     Decimal("3"),
            ...     Decimal("110")
            ... )
            Decimal('105')
        """
        if x0 == x1:
            raise ValueError("x0 and x1 cannot be equal")

        # y = y0 + (x - x0) * (y1 - y0) / (x1 - x0)
        slope = (y1 - y0) / (x1 - x0)
        result = y0 + (x - x0) * slope

        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def interpolate_curve(
        x: Decimal,
        points: Sequence[tuple[Decimal, Decimal]],
    ) -> Decimal:
        """Interpolate y value using curve of multiple points.

        Finds the two closest points and interpolates between them.

        Args:
            x: The x value to interpolate.
            points: Sequence of (x, y) tuples sorted by x.

        Returns:
            The interpolated y value.

        Raises:
            ValueError: If insufficient points provided.
        """
        Guard.not_empty(points, "points")

        if len(points) < 2:
            raise ValueError("At least 2 points required for interpolation")

        # Find bounding points
        x_values = [p[0] for p in points]

        # Check if x is outside range
        if x <= x_values[0]:
            return points[0][1]
        if x >= x_values[-1]:
            return points[-1][1]

        # Find surrounding points
        for i in range(len(points) - 1):
            if x_values[i] <= x <= x_values[i + 1]:
                x0, y0 = points[i]
                x1, y1 = points[i + 1]
                return LinearInterpolation.interpolate(x, x0, y0, x1, y1)

        raise ValueError("Unexpected error during interpolation")
