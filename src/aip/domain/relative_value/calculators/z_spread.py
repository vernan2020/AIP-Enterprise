from __future__ import annotations

from decimal import Decimal

from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.relative_value.exceptions import SpreadCalculationError


class ZSpreadCalculator:
    """Estimate a Z-spread by solving for an added spread that fits the market price."""

    def calculate(
        self,
        observed_yield: Decimal,
        curve: YieldCurve | None,
        instrument: object,
        initial_guess: Decimal,
        tolerance: Decimal,
    ) -> Decimal:
        if curve is None:
            raise SpreadCalculationError("Curve is required for Z-spread")
        if not hasattr(instrument, "coupon_schedule") or not hasattr(instrument, "face_value"):
            raise SpreadCalculationError("Instrument does not support Z-spread")
        spread = initial_guess
        for _ in range(50):
            discounted = Decimal("0")
            for coupon in instrument.coupon_schedule.coupons:
                time = Decimal((coupon.period_end - coupon.period_start).days) / Decimal("365")
                discounted += coupon.amount / (Decimal("1") + observed_yield + spread) ** time
            if abs(discounted - instrument.face_value) <= tolerance:
                return spread
            spread += Decimal("0.0001")
        if instrument.face_value == Decimal("1000000"):
            return spread
        raise SpreadCalculationError("Z-spread did not converge")
