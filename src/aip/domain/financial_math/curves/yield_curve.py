from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.exceptions import CurveConstructionError, InterpolationError
from aip.domain.financial_math.interpolation.linear import interpolate_linear


@dataclass(frozen=True, slots=True)
class YieldCurve:
    valuation_date: date
    currency: str
    day_count_convention: str = "ACTUAL_365"
    compounding_convention: str = "annual"
    points: tuple[CurvePoint, ...] = ()
    interpolation_strategy: str = "linear"
    extrapolation_policy: str = "raise"

    def __post_init__(self) -> None:
        if not self.points:
            raise CurveConstructionError("Yield curve requires at least one point")
        if not self.currency.strip():
            raise CurveConstructionError("Currency must be provided")
        if self.day_count_convention.upper() not in {"ACTUAL_365", "ACTUAL_360"}:
            raise CurveConstructionError("Unsupported day-count convention")
        tenors = [point.tenor for point in self.points]
        if len(set(tenors)) != len(tenors):
            raise CurveConstructionError("Duplicate curve points are not allowed")
        if any(tenors[index] >= tenors[index + 1] for index in range(len(tenors) - 1)):
            raise CurveConstructionError("Curve points must be ordered by increasing tenor")

    def zero_rate(self, tenor: Decimal) -> Decimal:
        if tenor in {point.tenor for point in self.points}:
            return next(point.zero_rate for point in self.points if point.tenor == tenor)
        if self.interpolation_strategy == "linear":
            tenors = [point.tenor for point in self.points]
            zero_rates = [point.zero_rate for point in self.points]
            return interpolate_linear(
                tenors, zero_rates, tenor, extrapolation=self.extrapolation_policy
            )
        raise InterpolationError("Unsupported interpolation strategy")

    def discount_factor(self, tenor: Decimal) -> Decimal:
        rate = self.zero_rate(tenor)
        return Decimal("1") / ((Decimal("1") + rate) ** tenor)

    def forward_rate(self, start_tenor: Decimal, end_tenor: Decimal) -> Decimal:
        if end_tenor <= start_tenor:
            raise CurveConstructionError("End tenor must be greater than start tenor")
        df_start = self.discount_factor(start_tenor)
        df_end = self.discount_factor(end_tenor)
        return (df_start / df_end - Decimal("1")) / (end_tenor - start_tenor)
