from enum import Enum


class CouponType(Enum):
    """Coupon structure type."""

    FIXED = "fixed"
    FLOATING = "floating"
    ZERO = "zero"
