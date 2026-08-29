from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.relative_value.exceptions import CurveNotAvailableError, SpreadCalculationError


class InterpolatedCurveSpreadCalculator:
    """Calculate interpolated reference-curve spread for a tenor."""

    def calculate(
        self, observed_yield: Decimal, curve: YieldCurve | None, tenor: Decimal
    ) -> Decimal:
        if curve is None:
            raise CurveNotAvailableError("Reference curve is unavailable")

        tenors = [point.tenor for point in curve.points]
        if tenor < min(tenors) or tenor > max(tenors):
            raise SpreadCalculationError("Curve interpolation failed")

        if tenor in tenors:
            reference_rate = curve.zero_rate(tenor)
        else:
            lower_tenors = [point.tenor for point in curve.points if point.tenor < tenor]
            if not lower_tenors:
                raise SpreadCalculationError("Curve interpolation failed")
            reference_rate = next(
                point.zero_rate for point in curve.points if point.tenor == max(lower_tenors)
            )

        return observed_yield - reference_rate
