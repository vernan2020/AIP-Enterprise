from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from aip.domain.instruments.bonds.bond import Bond


@dataclass(slots=True)
class ZeroCouponBond(Bond):
    """Zero-coupon bond."""

    def calculate_price(self) -> Decimal:
        return self.face_value / (Decimal("1") + self.yield_rate)

    def calculate_yield(self) -> Decimal:
        if self.yield_rate > 0:
            return self.yield_rate
        if self.clean_price <= 0:
            return Decimal("0")
        return self.face_value / self.clean_price - Decimal("1")
