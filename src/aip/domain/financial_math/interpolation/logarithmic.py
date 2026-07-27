from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_math.exceptions import InterpolationError


def interpolate_logarithmic(
    x_values: list[Decimal],
    y_values: list[Decimal],
    x: Decimal,
    *,
    extrapolation: str = "raise",
) -> Decimal:
    if len(x_values) != len(y_values):
        raise InterpolationError("X and Y value lists must have the same length")
    if len(x_values) < 2:
        raise InterpolationError("At least two points are required")
    if len(set(x_values)) != len(x_values):
        raise InterpolationError("Duplicate x values are not allowed")
    if x in x_values:
        return y_values[x_values.index(x)]
    if x < x_values[0] or x > x_values[-1]:
        if extrapolation == "constant":
            return y_values[0] if x < x_values[0] else y_values[-1]
        raise InterpolationError("Interpolation requested outside bounds")
    for index in range(len(x_values) - 1):
        if x_values[index] <= x <= x_values[index + 1]:
            x0, x1 = x_values[index], x_values[index + 1]
            y0, y1 = y_values[index], y_values[index + 1]
            if y0 <= 0 or y1 <= 0:
                raise InterpolationError("Logarithmic interpolation requires positive values")
            return y0 * ((y1 / y0) ** ((x - x0) / (x1 - x0)))
    raise InterpolationError("Interpolation point was not found")
