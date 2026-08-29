from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.relative_value.calculators.benchmark_spread import BenchmarkSpreadCalculator
from aip.domain.relative_value.calculators.interpolated_curve_spread import (
    InterpolatedCurveSpreadCalculator,
)
from aip.domain.relative_value.calculators.nominal_spread import NominalSpreadCalculator
from aip.domain.relative_value.calculators.z_spread import ZSpreadCalculator
from aip.domain.relative_value.exceptions import UnsupportedSpreadTypeError


class SpreadEngine:
    """Coordinate spread calculations for nominal, benchmark, curve, and Z-spread strategies."""

    def __init__(self) -> None:
        self._nominal = NominalSpreadCalculator()
        self._benchmark = BenchmarkSpreadCalculator()
        self._curve = InterpolatedCurveSpreadCalculator()
        self._z = ZSpreadCalculator()

    def calculate(
        self,
        spread_type: str,
        observed_yield: Decimal,
        benchmark_yield: Decimal | None = None,
        curve: YieldCurve | None = None,
        tenor: Decimal | None = None,
        instrument: object | None = None,
        initial_guess: Decimal | None = None,
        tolerance: Decimal | None = None,
    ) -> Decimal:
        if spread_type == "nominal":
            return self._nominal.calculate(observed_yield, benchmark_yield)
        if spread_type == "benchmark":
            return self._benchmark.calculate(observed_yield, benchmark_yield)
        if spread_type == "curve":
            if tenor is None:
                raise UnsupportedSpreadTypeError("Curve tenor is required")
            return self._curve.calculate(observed_yield, curve, tenor)
        if spread_type == "z":
            if instrument is None or initial_guess is None or tolerance is None:
                raise UnsupportedSpreadTypeError(
                    "Instrument, initial guess, and tolerance are required"
                )
            return self._z.calculate(observed_yield, curve, instrument, initial_guess, tolerance)
        raise UnsupportedSpreadTypeError(f"Unsupported spread type: {spread_type}")
