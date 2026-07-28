from __future__ import annotations

from decimal import Decimal

from aip.domain.liquidity.cashflow.exceptions import ProjectionError


class CouponProjection:
    """Compute the coupon cash flow amount from an instrument or simple nominal/rate inputs."""

    def project(self, nominal_value: Decimal | object, coupon_rate: Decimal | None = None) -> Decimal:
        if isinstance(nominal_value, (Decimal, int, float)):
            if coupon_rate is None:
                raise ProjectionError("Coupon rate is required for numeric projection")
            nominal = Decimal(str(nominal_value))
            rate = Decimal(str(coupon_rate))
            if nominal < 0:
                raise ProjectionError("Nominal value cannot be negative")
            if rate < 0:
                raise ProjectionError("Coupon rate cannot be negative")
            return nominal * rate

        instrument = nominal_value
        schedule = getattr(instrument, "coupon_schedule", None)
        if schedule is None:
            raise ProjectionError("Coupon schedule is required")

        coupon_type = getattr(instrument, "coupon_type", None)
        coupon_type_name = getattr(coupon_type, "value", coupon_type)
        if str(coupon_type_name).lower() in {"zero", "zero_coupon"}:
            return Decimal("0")
        if str(coupon_type_name).lower() not in {"fixed", "coupon", "float", "floating"}:
            raise ProjectionError("Unsupported coupon instrument")

        rate = getattr(instrument, "coupon_rate", None)
        if rate is None:
            raise ProjectionError("Coupon rate is required")
        rate = Decimal(str(rate))
        if rate < 0:
            raise ProjectionError("Coupon rate cannot be negative")

        total = sum((Decimal(str(coupon.amount)) for coupon in getattr(schedule, "coupons", ())), Decimal("0"))
        return total
